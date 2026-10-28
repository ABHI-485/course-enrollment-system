import requests
import streamlit as st
import pandas as pd
import altair as alt

API_URL = "http://127.0.0.1:8000"
TIMEOUT = 10

st.set_page_config(
    page_title="Course Enrollment System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Moderate styling: clean cards, readable spacing, and familiar Streamlit controls.
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.8rem; padding-bottom: 2.4rem;}
      [data-testid="stSidebar"] {border-right: 1px solid rgba(128,128,128,.22);}
      .app-subtitle {color: #8a93a5; margin-top: -0.55rem; margin-bottom: 1.25rem;}
      div[data-testid="stMetric"] {
        background: rgba(128,128,128,.075);
        border: 1px solid rgba(128,128,128,.18);
        padding: 16px 18px;
        border-radius: 12px;
        min-height: 108px;
      }
      div[data-testid="stMetricLabel"] {font-weight: 600;}
      div[data-testid="stMetricValue"] {font-size: 1.8rem; font-weight: 700;}
      div.stButton > button, div.stFormSubmitButton > button {
        border-radius: 8px; font-weight: 600; min-height: 2.55rem;
      }
      div[data-testid="stDataFrame"] {border-radius: 10px; overflow: hidden;}
      [data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- API helpers -----------------------------


def api_request(method, endpoint, **kwargs):
    """Call FastAPI and show a readable connection error."""
    try:
        return requests.request(
            method,
            f"{API_URL}{endpoint}",
            timeout=TIMEOUT,
            **kwargs,
        )
    except requests.RequestException as e:
        st.error(
            f"API connection error: {type(e).__name__}: {e}"
        )
        return None



def error_text(response):
    """Convert FastAPI/Pydantic error payloads to readable text."""
    try:
        detail = response.json().get("detail", response.text)
    except (ValueError, AttributeError):
        return f"Error {response.status_code}: {response.text}"

    if isinstance(detail, list):
        messages = []
        for item in detail:
            field = " → ".join(
                str(part) for part in item.get("loc", []) if part != "body"
            )
            message = item.get("msg", "Invalid value")
            messages.append(f"{field}: {message}" if field else message)
        return "; ".join(messages)
    return str(detail)


def flash(kind, message):
    """Store a message so it survives st.rerun()."""
    st.session_state.setdefault("flash_messages", []).append((kind, message))


def show_flash():
    """Display and clear stored messages."""
    for kind, message in st.session_state.pop("flash_messages", []):
        if kind == "success":
            st.success(message)
        elif kind == "warning":
            st.warning(message)
        else:
            st.error(message)


def fetch_list(endpoint, label):
    """GET a list from the backend. Returns a list, or None on failure."""
    response = api_request("GET", endpoint)

    if response is None:
        return None

    if not response.ok:
        st.error(f"Could not load {label}: {error_text(response)}")
        return None

    try:
        result = response.json()

        if isinstance(result, list):
            return result

        st.error(f"Unexpected response format while loading {label}.")
        return None

    except ValueError:
        st.error(f"Invalid JSON response while loading {label}.")
        return None


# ----------------------------- Small helpers -----------------------------

def calc_new_seats(old_capacity, old_seats, new_capacity):
    """New seats_available after a capacity change, or None if the new
    capacity is below the seats already taken."""
    occupied = old_capacity - old_seats
    if new_capacity < occupied:
        return None
    return new_capacity - occupied


def course_label(course):
    return (
        f"#{course['id']} · {course['title']} "
        f"({course['seats_available']}/{course['capacity']} seats free)"
    )


def student_label(student):
    return f"#{student['id']} · {student['name']} ({student['email']})"


def courses_table(courses):
    return pd.DataFrame(
        [
            {
                "ID": c["id"],
                "Title": c["title"],
                "Description": c["description"],
                "Capacity": c["capacity"],
                "Seats available": c["seats_available"],
                "Seats taken": c["capacity"] - c["seats_available"],
                "Fee": float(c["fee"]),
            }
            for c in courses
        ]
    )


def students_table(students):
    return pd.DataFrame(
        [{"ID": s["id"], "Name": s["name"], "Email": s["email"]} for s in students]
    )


def delete_with_confirm(kind, items, label_fn, name_fn, endpoint_base):
    """Shared delete UI for courses and students."""
    if not items:
        st.info(f"There are no {kind}s to delete.")
        return
    doomed = st.selectbox(
        f"Select a {kind} to delete",
        items,
        format_func=label_fn,
        key=f"delete_{kind}_select",
    )
    st.warning(
        f"Deleting is permanent. A {kind} with any enrollment history "
        "(even cancelled) cannot be deleted."
    )
    confirm = st.checkbox(
        f"Yes, delete '{name_fn(doomed)}'",
        key=f"confirm_del_{kind}_{doomed['id']}",
    )
    if st.button(f"Delete {kind}", disabled=not confirm):
        response = api_request("DELETE", f"{endpoint_base}/{doomed['id']}")
        if response is not None:
            if response.ok:
                flash("success", f"{kind.capitalize()} '{name_fn(doomed)}' deleted.")
                st.rerun()
            else:
                st.error(error_text(response))


# ----------------------------- Page layout -----------------------------

st.title("🎓 Course Enrollment System")
st.markdown(
    '<p class="app-subtitle">Manage courses, students, and enrollments.</p>',
    unsafe_allow_html=True,
)

st.sidebar.title("🎓 Course Enrollment")
st.sidebar.caption("Course and student management")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Courses", "Students", "Enrollments"],
    label_visibility="collapsed",
    key="main_navigation",
)
st.sidebar.divider()
st.sidebar.caption("FastAPI · PostgreSQL · Streamlit")

show_flash()


# ------------------------------- HOME -------------------------------

if page == "Dashboard":
    st.subheader("Dashboard overview")
    st.caption("A clear snapshot of courses, student registrations, enrollments, and seat usage.")

    courses = fetch_list("/courses", "courses")
    students = fetch_list("/students", "students")

    if courses is None or students is None:
        st.warning("The dashboard could not load all data. Check that FastAPI and PostgreSQL are running, then refresh this page.")
    else:
        # Collect enrollment history through the API endpoint already used by this project.
        enrollment_map = {}
        enrollment_load_failed = False
        for student in students:
            response = api_request("GET", f"/enrollments/student/{student['id']}")
            if response is None or not response.ok:
                enrollment_load_failed = True
                continue
            try:
                records = response.json()
                if isinstance(records, list):
                    for record in records:
                        if "id" in record:
                            enrollment_map[record["id"]] = record
            except (ValueError, TypeError):
                enrollment_load_failed = True

        all_enrollments = list(enrollment_map.values())
        active_enrollments = [e for e in all_enrollments if e.get("status") == "active"]
        cancelled_enrollments = [e for e in all_enrollments if e.get("status") == "cancelled"]
        total_capacity = sum(int(c.get("capacity", 0)) for c in courses)
        available_seats = sum(int(c.get("seats_available", 0)) for c in courses)
        occupied_seats = max(total_capacity - available_seats, 0)
        utilization = (occupied_seats / total_capacity * 100) if total_capacity else 0

        # Summary cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total courses", len(courses), help="Courses currently stored in the database.")
        m2.metric("Registered students", len(students), help="Students currently registered in the system.")
        m3.metric("Active enrollments", len(active_enrollments), help="Enrollments whose status is active.")
        m4.metric("Seats available", available_seats, help="Total seats remaining across all courses.")

        if enrollment_load_failed:
            st.info("Some enrollment records could not be loaded, so enrollment charts may be incomplete.")

        st.divider()
        chart_left, chart_right = st.columns([1.35, 1])

        with chart_left:
            st.markdown("#### Active enrollments by course")
            if not courses:
                st.info("No courses yet. Add a course from the Courses page to see course analytics.")
            else:
                active_by_course = {c["id"]: 0 for c in courses}
                for enrollment in active_enrollments:
                    course_id = enrollment.get("course_id")
                    if course_id in active_by_course:
                        active_by_course[course_id] += 1

                course_chart_data = pd.DataFrame([
                    {
                        "Course": c.get("title", f"Course #{c.get('id', '')}"),
                        "Active enrollments": active_by_course.get(c["id"], 0),
                    }
                    for c in courses
                ]).sort_values("Active enrollments", ascending=False)

                course_chart = (
                    alt.Chart(course_chart_data)
                    .mark_bar(cornerRadiusEnd=5, size=22)
                    .encode(
                        x=alt.X("Active enrollments:Q", title="Active students", axis=alt.Axis(tickMinStep=1)),
                        y=alt.Y("Course:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                        tooltip=[
                            alt.Tooltip("Course:N", title="Course"),
                            alt.Tooltip("Active enrollments:Q", title="Active enrollments"),
                        ],
                    )
                    .properties(height=max(150, min(360, 42 * len(course_chart_data))))
                )
                st.altair_chart(course_chart, use_container_width=True)

        with chart_right:
            st.markdown("#### Enrollment status")
            status_chart_data = pd.DataFrame([
                {"Status": "Active", "Records": len(active_enrollments)},
                {"Status": "Cancelled", "Records": len(cancelled_enrollments)},
            ])
            status_chart = (
                alt.Chart(status_chart_data)
                .mark_bar(cornerRadiusEnd=5, size=30)
                .encode(
                    x=alt.X("Records:Q", title="Number of records", axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("Status:N", sort=["Active", "Cancelled"], title=None),
                    tooltip=[
                        alt.Tooltip("Status:N", title="Status"),
                        alt.Tooltip("Records:Q", title="Records"),
                    ],
                )
                .properties(height=150)
            )
            st.altair_chart(status_chart, use_container_width=True)
            st.caption(f"{len(active_enrollments)} active · {len(cancelled_enrollments)} cancelled · {len(all_enrollments)} total records")

        st.divider()
        st.markdown("#### Course seat capacity")
        cap_col, progress_col = st.columns([1, 2])
        with cap_col:
            st.metric("Overall seat utilization", f"{utilization:.1f}%", help="Occupied seats divided by total course capacity.")
            st.caption(f"{occupied_seats} seats occupied out of {total_capacity} total")
        with progress_col:
            st.caption("Overall capacity used")
            st.progress(min(max(utilization / 100, 0.0), 1.0))
            st.caption(f"{available_seats} seats remain available across all courses.")

        if courses:
            capacity_rows = []
            for course in courses:
                capacity = int(course.get("capacity", 0))
                available = int(course.get("seats_available", 0))
                taken = max(capacity - available, 0)
                capacity_rows.append({
                    "Course": course.get("title", "Untitled"),
                    "Capacity": capacity,
                    "Seats taken": taken,
                    "Seats available": available,
                    "Utilization (%)": round((taken / capacity * 100), 1) if capacity else 0,
                })
            st.dataframe(pd.DataFrame(capacity_rows), use_container_width=True, hide_index=True)
            full_courses = [c.get("title", "Untitled") for c in courses if int(c.get("seats_available", 0)) <= 0]
            if full_courses:
                st.warning("Full courses: " + ", ".join(full_courses))

        with st.expander("Recent enrollment records"):
            if all_enrollments:
                student_lookup = {item["id"]: item for item in students}
                course_lookup = {item["id"]: item for item in courses}
                recent_rows = []
                for record in sorted(all_enrollments, key=lambda item: item.get("id", 0), reverse=True)[:10]:
                    student = student_lookup.get(record.get("student_id"), {})
                    course = course_lookup.get(record.get("course_id"), {})
                    recent_rows.append({
                        "Enrollment ID": record.get("id"),
                        "Student": student.get("name", f"#{record.get('student_id', '')}"),
                        "Course": course.get("title", f"#{record.get('course_id', '')}"),
                        "Status": str(record.get("status", "unknown")).title(),
                    })
                st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No enrollment records yet. Enroll a student to populate this section.")

    st.caption("Use the sidebar to manage courses, students, and enrollments.")

elif page == "Courses":
    st.subheader("Courses")
    st.caption("Search the catalogue, manage course details, and control seat capacity.")

    loaded_courses = fetch_list("/courses", "courses")
    courses = loaded_courses if loaded_courses is not None else []

    if loaded_courses is not None and courses:
        search_text = st.text_input(
            "Search courses",
            placeholder="Search by course ID, title, or description...",
            key="course_search_text",
        ).strip().lower()
        visible_courses = [
            course for course in courses
            if search_text in str(course.get("id", "")).lower()
            or search_text in str(course.get("title", "")).lower()
            or search_text in str(course.get("description") or "").lower()
        ]
        st.caption(f"Showing {len(visible_courses)} of {len(courses)} courses")
        if visible_courses:
            st.dataframe(courses_table(visible_courses), use_container_width=True, hide_index=True)
        else:
            st.info("No courses match your search.")
    elif loaded_courses is not None:
        st.info("No courses found. Create your first course below.")

    tab_create, tab_update, tab_delete = st.tabs(
        ["➕ Create", "✏️ Update", "🗑️ Delete"]
    )

    with tab_create:
        st.markdown("#### Add a course")
        with st.form("create_course_form", clear_on_submit=True):
            title = st.text_input("Course title", placeholder="e.g. Python Programming")
            description = st.text_area("Description", placeholder="What will students learn?")
            capacity_col, fee_col = st.columns(2)
            with capacity_col:
                capacity = st.number_input("Seat capacity", min_value=1, value=10, step=1)
            with fee_col:
                fee = st.number_input("Course fee (₹)", min_value=0.0, value=499.0, step=100.0, format="%.2f")
            submitted = st.form_submit_button("Create course", type="primary", use_container_width=True)

        if submitted:
            if len(title.strip()) < 2:
                st.error("Course title must be at least 2 characters.")
            else:
                response = api_request(
                    "POST",
                    "/courses",
                    json={
                        "title": title.strip(),
                        "description": description.strip() or None,
                        "capacity": int(capacity),
                        "fee": round(float(fee), 2),
                    },
                )
                if response is not None:
                    if response.status_code == 201:
                        flash("success", f"Course '{title.strip()}' created.")
                        st.rerun()
                    else:
                        st.error(error_text(response))

    with tab_update:
        if not courses:
            st.info("There are no courses to update yet. Create a course first.")
        else:
            st.markdown("#### Update a course using its ID")
            st.caption("Select the existing course, then enter a new unused Course ID if you need to change it. Enrollment history will follow the ID change.")

            course_by_id = {int(course["id"]): course for course in courses}
            course_ids = sorted(course_by_id)
            cid = st.selectbox(
                "Select Course ID",
                options=course_ids,
                format_func=lambda course_id: f"ID #{course_id} — {course_by_id[course_id]['title']}",
                key="update_course_id_select_" + "_".join(map(str, course_ids)),
            )
            chosen = course_by_id[int(cid)]
            taken = int(chosen["capacity"]) - int(chosen["seats_available"])

            with st.form(f"update_course_form_{cid}"):
                st.markdown("##### Course ID")
                new_course_id = st.number_input(
                    "Course ID (editable)",
                    min_value=1,
                    value=int(cid),
                    step=1,
                    help="Enter an unused positive ID. Existing enrollment references will follow the ID change.",
                    key=f"u_course_id_{cid}",
                )
                st.caption(
                    "You can keep the current ID or enter a different unused ID. "
                    "The ID must not already belong to another course."
                )
                title_col, fee_col = st.columns([2, 1])
                with title_col:
                    new_title = st.text_input("Course title", value=chosen["title"], key=f"u_title_{cid}")
                with fee_col:
                    new_fee = st.number_input("Course fee (₹)", min_value=0.0, value=float(chosen["fee"]), step=100.0, format="%.2f", key=f"u_fee_{cid}")
                new_description = st.text_area("Description", value=chosen.get("description") or "", key=f"u_desc_{cid}")
                capacity_col, seats_col = st.columns(2)
                with capacity_col:
                    new_capacity = st.number_input("Seat capacity", min_value=1, value=int(chosen["capacity"]), step=1, key=f"u_cap_{cid}")
                with seats_col:
                    st.text_input("Active enrollments", value=str(taken), disabled=True, key=f"u_taken_{cid}")
                st.caption(f"Capacity cannot be lower than {taken} occupied seat(s).")
                save = st.form_submit_button("Save course changes", type="primary", use_container_width=True)

            if save:
                new_seats = calc_new_seats(int(chosen["capacity"]), int(chosen["seats_available"]), int(new_capacity))
                if len(new_title.strip()) < 2:
                    st.error("Course title must be at least 2 characters.")
                elif new_seats is None:
                    st.error(f"Capacity cannot be lower than the {taken} seat(s) already taken by active enrollments.")
                else:
                    response = api_request(
                        "PUT",
                        f"/courses/{cid}",
                        json={
                            "id": int(new_course_id),
                            "title": new_title.strip(),
                            "description": new_description.strip() or None,
                            "capacity": int(new_capacity),
                            "seats_available": new_seats,
                            "fee": round(float(new_fee), 2),
                        },
                    )
                    if response is not None:
                        if response.ok:
                            if int(new_course_id) != int(cid):
                                flash(
                                    "success",
                                    f"Course ID changed from #{cid} to #{int(new_course_id)}; course details and enrollment references were updated.",
                                )
                            else:
                                flash("success", f"Course ID #{cid} updated successfully.")
                            st.rerun()
                        else:
                            st.error(error_text(response))

    with tab_delete:
        delete_with_confirm(
            "course", courses, course_label, lambda c: c["title"], "/courses"
        )


# ------------------------------ STUDENTS ------------------------------

elif page == "Students":
    st.subheader("Students")
    st.caption("Register students, update a record by ID, and manage student details.")

    loaded_students = fetch_list("/students", "students")
    students = loaded_students if loaded_students is not None else []

    if loaded_students is not None:
        metric_col, metric_col2 = st.columns(2)
        metric_col.metric("Registered students", len(students))
        unique_emails = len({str(s.get("email", "")).strip().lower() for s in students if s.get("email")})
        metric_col2.metric("Unique email addresses", unique_emails)

        if students:
            student_search = st.text_input(
                "Search students",
                placeholder="Search by student ID, name, or email...",
                key="student_search_text",
            ).strip().lower()
            visible_students = [
                student for student in students
                if student_search in str(student.get("id", "")).lower()
                or student_search in str(student.get("name", "")).lower()
                or student_search in str(student.get("email", "")).lower()
            ]
            st.caption(f"Showing {len(visible_students)} of {len(students)} students")
            if visible_students:
                st.dataframe(students_table(visible_students), use_container_width=True, hide_index=True)
            else:
                st.info("No students match your search.")
        else:
            st.info("No students registered yet. Register your first student below.")

    tab_create, tab_update, tab_delete = st.tabs(
        ["➕ Register", "✏️ Update by ID", "🗑️ Delete"]
    )

    with tab_create:
        st.markdown("#### Register a student")
        with st.form("create_student_form", clear_on_submit=True):
            name_col, email_col = st.columns(2)
            with name_col:
                name = st.text_input("Student name", placeholder="e.g. Rahul Patil")
            with email_col:
                email = st.text_input("Student email", placeholder="name@example.com")
            submitted = st.form_submit_button("Register student", type="primary", use_container_width=True)

        if submitted:
            if len(name.strip()) < 2:
                st.error("Student name must be at least 2 characters.")
            elif not email.strip() or "@" not in email.strip() or "." not in email.strip().split("@")[-1]:
                st.error("Please enter a valid email address.")
            else:
                response = api_request(
                    "POST",
                    "/students",
                    json={"name": name.strip(), "email": email.strip()},
                )
                if response is not None:
                    if response.status_code == 201:
                        flash("success", f"Student '{name.strip()}' registered.")
                        st.rerun()
                    else:
                        st.error(error_text(response))

    with tab_update:
        if not students:
            st.info("There are no students to update yet. Register a student first.")
        else:
            st.markdown("#### Update a student using their ID")
            st.caption("Select the student ID shown in the table. The ID is fixed; only the name and email can be changed.")

            student_by_id = {int(student["id"]): student for student in students}
            student_ids = sorted(student_by_id)
            sid = st.selectbox(
                "Select Student ID",
                options=student_ids,
                format_func=lambda student_id: f"ID #{student_id} — {student_by_id[student_id]['name']} ({student_by_id[student_id]['email']})",
                key="update_student_id_select",
            )
            chosen = student_by_id[int(sid)]

            with st.form(f"update_student_form_{sid}"):
                st.text_input("Student ID (read-only)", value=str(sid), disabled=True, key=f"s_id_display_{sid}")
                new_name_col, new_email_col = st.columns(2)
                with new_name_col:
                    new_name = st.text_input("Student name", value=chosen["name"], key=f"s_name_{sid}")
                with new_email_col:
                    new_email = st.text_input("Student email", value=chosen["email"], key=f"s_email_{sid}")
                save = st.form_submit_button("Save student changes", type="primary", use_container_width=True)

            if save:
                if len(new_name.strip()) < 2:
                    st.error("Student name must be at least 2 characters.")
                elif not new_email.strip() or "@" not in new_email.strip() or "." not in new_email.strip().split("@")[-1]:
                    st.error("Please enter a valid email address.")
                else:
                    response = api_request(
                        "PUT",
                        f"/students/{sid}",
                        json={"name": new_name.strip(), "email": new_email.strip()},
                    )
                    if response is not None:
                        if response.ok:
                            flash("success", f"Student ID #{sid} updated successfully.")
                            st.rerun()
                        else:
                            st.error(error_text(response))

    with tab_delete:
        delete_with_confirm(
            "student", students, student_label, lambda s: s["name"], "/students"
        )


# ----------------------------- ENROLLMENTS -----------------------------

elif page == "Enrollments":
    st.subheader("Enrollments")
    st.caption("Create enrollments, review history by student or course, and cancel active enrollments.")

    students = fetch_list("/students", "students")
    courses = fetch_list("/courses", "courses")

    if students is None or courses is None:
        st.stop()

    student_by_id = {int(s["id"]): s for s in students}
    course_by_id = {int(c["id"]): c for c in courses}

    if not students or not courses:
        st.info("You need at least one student and one course to create and search enrollments.")
        st.stop()

    # Create an enrollment
    with st.container(border=True):
        st.markdown("#### ➕ Enroll a student")
        with st.form("enroll_form"):
            student_col, course_col = st.columns(2)
            with student_col:
                pick_student = st.selectbox("Student", students, format_func=student_label, key="enroll_student_select")
            with course_col:
                pick_course = st.selectbox("Course", courses, format_func=course_label, key="enroll_course_select")
            if pick_course.get("seats_available", 0) <= 0:
                st.warning("The selected course is currently full.")
            submitted = st.form_submit_button("Create enrollment", type="primary", use_container_width=True)

        if submitted:
            sid, cid = int(pick_student["id"]), int(pick_course["id"])
            if int(pick_course.get("seats_available", 0)) <= 0:
                st.error(f"'{pick_course['title']}' is full. No seats are available.")
            else:
                existing = api_request("GET", f"/enrollments/student/{sid}")
                if existing is None:
                    pass
                elif not existing.ok:
                    st.error(error_text(existing))
                else:
                    try:
                        existing_rows = existing.json()
                    except ValueError:
                        existing_rows = []
                        st.error("The API returned invalid enrollment data.")
                    else:
                        already_active = any(
                            int(e.get("course_id", -1)) == cid and e.get("status") == "active"
                            for e in existing_rows
                        )
                        if already_active:
                            st.error(f"{pick_student['name']} is already actively enrolled in '{pick_course['title']}'.")
                        else:
                            response = api_request(
                                "POST", "/enroll", json={"student_id": sid, "course_id": cid}
                            )
                            if response is not None:
                                if response.status_code == 201:
                                    fresh = api_request("GET", f"/courses/{cid}")
                                    note = ""
                                    if fresh is not None and fresh.ok:
                                        latest = fresh.json()
                                        note = f" Seats remaining: {latest.get('seats_available', '?')}/{latest.get('capacity', '?')}."
                                    flash("success", f"Enrollment created for {pick_student['name']} in '{pick_course['title']}'.{note}")
                                    st.rerun()
                                else:
                                    st.error(error_text(response))

    st.divider()
    st.markdown("#### 🔎 Find enrollment records")
    filter_col1, filter_col2 = st.columns([1, 1])
    with filter_col1:
        search_type = st.radio("Search by", ["Student", "Course"], horizontal=True, key="enrollment_search_type")
    with filter_col2:
        status_filter = st.radio("Status", ["All", "Active", "Cancelled"], horizontal=True, key="enrollment_status_filter")

    if search_type == "Student":
        target = st.selectbox("Student", students, format_func=student_label, key="search_student")
        endpoint = f"/enrollments/student/{target['id']}"
    else:
        target = st.selectbox("Course", courses, format_func=course_label, key="search_course")
        endpoint = f"/enrollments/course/{target['id']}"

    all_results = fetch_list(endpoint, "enrollments") or []
    active_for_scope = [r for r in all_results if r.get("status") == "active"]
    cancelled_for_scope = [r for r in all_results if r.get("status") == "cancelled"]

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Total records", len(all_results))
    metric2.metric("Active", len(active_for_scope))
    metric3.metric("Cancelled", len(cancelled_for_scope))

    visible_results = all_results
    if status_filter != "All":
        visible_results = [r for r in all_results if r.get("status", "").lower() == status_filter.lower()]

    if visible_results:
        rows = []
        for record in visible_results:
            sid = int(record.get("student_id", -1))
            cid = int(record.get("course_id", -1))
            student = student_by_id.get(sid, {})
            course = course_by_id.get(cid, {})
            rows.append({
                "Enrollment ID": record.get("id"),
                "Student ID": sid,
                "Student": student.get("name", f"#{sid}"),
                "Email": student.get("email", ""),
                "Course ID": cid,
                "Course": course.get("title", f"#{cid}"),
                "Status": str(record.get("status", "unknown")).title(),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(f"No {status_filter.lower() if status_filter != 'All' else ''} enrollment records found for this selection.".replace("  ", " "))

    st.divider()
    st.markdown("#### Cancel an enrollment")
    if not active_for_scope:
        st.info("There are no active enrollments for the selected student or course.")
    else:
        def enrollment_label(record):
            sid = int(record.get("student_id", -1))
            cid = int(record.get("course_id", -1))
            student = student_by_id.get(sid, {})
            course = course_by_id.get(cid, {})
            return f"Enrollment ID #{record['id']} · Student #{sid} {student.get('name', '')} → Course #{cid} {course.get('title', '')}"

        to_cancel = st.selectbox(
            "Select an active enrollment to cancel",
            active_for_scope,
            format_func=enrollment_label,
            key="cancel_select",
        )
        st.warning("Cancellation preserves the enrollment history and restores one available seat in the course.")
        confirm = st.checkbox(
            f"I confirm cancellation of Enrollment ID #{to_cancel['id']}",
            key=f"confirm_cancel_{to_cancel['id']}",
        )
        if st.button("Cancel enrollment", type="primary", disabled=not confirm):
            response = api_request("DELETE", f"/enrollments/{to_cancel['id']}")
            if response is not None:
                if response.ok:
                    fresh = api_request("GET", f"/courses/{to_cancel['course_id']}")
                    note = ""
                    if fresh is not None and fresh.ok:
                        latest = fresh.json()
                        note = f" Seat restored: '{latest.get('title', 'course')}' now has {latest.get('seats_available', '?')}/{latest.get('capacity', '?')} seats available."
                    flash("success", f"Enrollment ID #{to_cancel['id']} cancelled.{note}")
                    st.rerun()
                else:
                    st.error(error_text(response))

