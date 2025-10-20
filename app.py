import streamlit as st
import pandas as pd
from fpdf import FPDF
import json
import os
from sqlalchemy import create_engine, text

# Database connection (using secrets for security)
DB_URL = st.secrets["DB_URL"]
engine = create_engine(DB_URL)

def init_db():
    with engine.connect() as conn:
        # Consultants table
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS public.consultants (
                role TEXT PRIMARY KEY,
                annual_salary REAL,
                fixed_cost REAL
            )
        '''))
        # Default consultants if table is empty
        defaults = [
            ('Strategy Consultant', 27000, 500),
            ('Senior Strategy Consultant', 40000, 1000),
            ('IT Consultant', 24000, 500),
            ('Senior IT Consultant', 37000, 1000)
        ]
        for default in defaults:
            conn.execute(text('''
                INSERT INTO public.consultants (role, annual_salary, fixed_cost)
                VALUES (:role, :salary, :fixed)
                ON CONFLICT (role) DO NOTHING
            '''), {'role': default[0], 'salary': default[1], 'fixed': default[2]})
        # Projects table
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS public.projects (
                id SERIAL PRIMARY KEY,
                name TEXT,
                duration INTEGER,
                sales_price REAL,
                consultants_json TEXT
            )
        '''))
        conn.commit()

init_db()

# Helper functions
def get_consultants():
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM public.consultants"), conn)
    return df

def calculate_costs(duration, assignments):
    consultants = get_consultants()
    total_cost = 0
    for role, count in assignments.items():
        if count > 0:
            row = consultants[consultants['role'] == role].iloc[0]
            daily_cost = row['annual_salary'] / 220
            role_cost = (daily_cost * duration * count) + (row['fixed_cost'] * count)
            total_cost += role_cost
    return total_cost

def save_project(name, duration, sales_price, assignments):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO public.projects (name, duration, sales_price, consultants_json)
            VALUES (:name, :duration, :sales_price, :consultants_json)
        '''), {
            'name': name,
            'duration': duration,
            'sales_price': sales_price,
            'consultants_json': json.dumps(assignments)
        })
        conn.commit()

def update_project(project_id, name, duration, sales_price, assignments):
    with engine.connect() as conn:
        conn.execute(text('''
            UPDATE public.projects
            SET name=:name, duration=:duration, sales_price=:sales_price, consultants_json=:consultants_json
            WHERE id=:id
        '''), {
            'name': name,
            'duration': duration,
            'sales_price': sales_price,
            'consultants_json': json.dumps(assignments),
            'id': project_id
        })
        conn.commit()

def delete_project(project_id):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM public.projects WHERE id=:id"), {'id': project_id})
        conn.commit()

def get_projects():
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT * FROM public.projects"), conn)
    return df

def add_consultant(role, annual_salary, fixed_cost):
    with engine.connect() as conn:
        conn.execute(text('''
            INSERT INTO public.consultants (role, annual_salary, fixed_cost)
            VALUES (:role, :annual_salary, :fixed_cost)
            ON CONFLICT (role) DO UPDATE SET
                annual_salary = EXCLUDED.annual_salary,
                fixed_cost = EXCLUDED.fixed_cost
        '''), {
            'role': role,
            'annual_salary': annual_salary,
            'fixed_cost': fixed_cost
        })
        conn.commit()

def delete_consultant(role):
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM public.consultants WHERE role=:role"), {'role': role})
        conn.commit()

def export_to_excel(df, filename):
    df.to_excel(filename, index=False)
    return filename

def export_to_pdf(df, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for col in df.columns:
        pdf.cell(40, 10, str(col), 1)
    pdf.ln()
    for _, row in df.iterrows():
        for val in row:
            pdf.cell(40, 10, str(val), 1)
        pdf.ln()
    pdf.output(filename)
    return filename

# App layout
st.set_page_config(page_title="Consulting Project Evaluator", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "test" and password == "test":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid credentials")
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["New Project", "Saved Projects", "Manage Consultants"])

    # Add consistent title on each page
    st.markdown("<h1 style='text-align: center; color: #2c3e50; font-family: Arial;'>Consulting Project Evaluator</h1>", unsafe_allow_html=True)

    if page == "New Project":
        st.title("New Project Evaluation")
        with st.form(key="project_form"):
            project_name = st.text_input("Project Name (for saving)")
            duration = st.number_input("Project Duration (days)", min_value=1, value=30)
            sales_price = st.number_input("Proposed Sales Price (€)", min_value=0.0, value=10000.0)
            st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Assign Consultants</h3>", unsafe_allow_html=True)
            consultants = get_consultants()
            assignments = {}
            cols = st.columns(2)
            for i, (_, row) in enumerate(consultants.iterrows()):
                with cols[i % 2]:
                    count = st.number_input(f"Number of {row['role']}", min_value=0, value=0, step=1)
                    assignments[row['role']] = count
            submit = st.form_submit_button("Calculate")
        
        if submit:
            total_cost = calculate_costs(duration, assignments)
            profit = sales_price - total_cost
            margin = (profit / sales_price * 100) if sales_price > 0 else 0
            st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Results</h3>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"<div style='background-color: #e74c3c; color: white; padding: 10px; border-radius: 5px;'>Total Costs: €{total_cost:.2f}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background-color: #2ecc71; color: white; padding: 10px; border-radius: 5px;'>Profit: €{profit:.2f}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background-color: #3498db; color: white; padding: 10px; border-radius: 5px;'>Margin: {margin:.2f}%</div>", unsafe_allow_html=True)
            
            if st.button("Save Project"):
                if not project_name:
                    st.error("Please enter a project name to save.")
                else:
                    save_project(project_name, duration, sales_price, assignments)
                    st.success("Project saved!")

    elif page == "Saved Projects":
        st.title("Saved Projects")
        projects = get_projects()
        if not projects.empty:
            for _, row in projects.iterrows():
                with st.expander(f"Project: {row['name']} (ID: {row['id']})"):
                    st.write(f"Duration: {row['duration']} days")
                    st.write(f"Sales Price: €{row['sales_price']:.2f}")
                    assignments = json.loads(row['consultants_json'])
                    total_cost = calculate_costs(row['duration'], assignments)
                    profit = row['sales_price'] - total_cost
                    margin = (profit / row['sales_price'] * 100) if row['sales_price'] > 0 else 0
                    st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Results</h3>", unsafe_allow_html=True)
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"<div style='background-color: #e74c3c; color: white; padding: 10px; border-radius: 5px;'>Total Costs: €{total_cost:.2f}</div>", unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"<div style='background-color: #2ecc71; color: white; padding: 10px; border-radius: 5px;'>Profit: €{profit:.2f}</div>", unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"<div style='background-color: #3498db; color: white; padding: 10px; border-radius: 5px;'>Margin: {margin:.2f}%</div>", unsafe_allow_html=True)
                    st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Assigned Consultants</h3>", unsafe_allow_html=True)
                    for role, count in assignments.items():
                        if count > 0:
                            st.write(f"{role}: {count}")
                    
                    # Edit form
                    with st.form(key=f"edit_{row['id']}"):
                        new_name = st.text_input("Edit Name", value=row['name'])
                        new_duration = st.number_input("Edit Duration", min_value=1, value=int(row['duration']))
                        new_sales = st.number_input("Edit Sales Price", min_value=0.0, value=float(row['sales_price']))
                        new_assign = {}
                        consultants = get_consultants()
                        cols = st.columns(2)
                        for i, (_, c_row) in enumerate(consultants.iterrows()):
                            with cols[i % 2]:
                                count = st.number_input(f"Edit {c_row['role']}", min_value=0, value=assignments.get(c_row['role'], 0))
                                new_assign[c_row['role']] = count
                        if st.form_submit_button("Update"):
                            update_project(row['id'], new_name, new_duration, new_sales, new_assign)
                            st.success("Updated!")
                            st.rerun()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Delete", key=f"del_{row['id']}"):
                            delete_project(row['id'])
                            st.success("Deleted!")
                            st.rerun()
                    with col2:
                        df_single = pd.DataFrame([{
                            'Name': row['name'], 'Duration': row['duration'], 'Sales Price': row['sales_price'],
                            'Total Cost': total_cost, 'Profit': profit, 'Margin': margin
                        }])
                        excel_file = export_to_excel(df_single, f"{row['name']}.xlsx")
                        if excel_file:
                            with open(excel_file, "rb") as f:
                                st.download_button("Export to Excel", f, file_name=f"{row['name']}.xlsx")
                            os.remove(excel_file)  # Clean up file
                    with col3:
                        pdf_file = export_to_pdf(df_single, f"{row['name']}.pdf")
                        if pdf_file:
                            with open(pdf_file, "rb") as f:
                                st.download_button("Export to PDF", f, file_name=f"{row['name']}.pdf")
                            os.remove(pdf_file)  # Clean up file
            
            # Export all
            st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Export All Projects</h3>", unsafe_allow_html=True)
            all_df = projects.copy()
            all_df['consultants'] = all_df['consultants_json'].apply(json.loads)
            all_df = all_df.drop('consultants_json', axis=1)  # Simplify for export
            col1, col2 = st.columns(2)
            with col1:
                all_excel = export_to_excel(all_df, "all_projects.xlsx")
                if all_excel:
                    with open(all_excel, "rb") as f:
                        st.download_button("Export All to Excel", f, file_name="all_projects.xlsx")
                    os.remove(all_excel)  # Clean up
            with col2:
                all_pdf = export_to_pdf(all_df, "all_projects.pdf")
                if all_pdf:
                    with open(all_pdf, "rb") as f:
                        st.download_button("Export All to PDF", f, file_name="all_projects.pdf")
                    os.remove(all_pdf)  # Clean up
        else:
            st.info("No saved projects yet.")

    elif page == "Manage Consultants":
        st.title("Manage Consultants")
        consultants = get_consultants()
        consultants.index = consultants.index + 1
        st.dataframe(consultants)
        st.markdown("""
            <style>
            .stDataFrame tr:nth-child(even) {background-color: #f2f2f2;}
            .stDataFrame th {background-color: #3498db; color: white;}
            </style>
            """, unsafe_allow_html=True)
        
        st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Add or Edit Role</h3>", unsafe_allow_html=True)
        with st.form(key="consultant_form"):
            role = st.text_input("Role Name")
            salary = st.number_input("Annual Salary (€)", min_value=0.0)
            fixed = st.number_input("Fixed Cost (€)", min_value=0.0)
            if st.form_submit_button("Add/Update"):
                if not role:
                    st.error("Please enter a role name.")
                else:
                    add_consultant(role, salary, fixed)
                    st.success("Saved!")
                    st.rerun()
        
        st.markdown("<h3 style='border-bottom: 2px solid #3498db; padding-bottom: 5px;'>Delete Role</h3>", unsafe_allow_html=True)
        if not consultants.empty:
            role_to_delete = st.selectbox("Select Role to Delete", consultants['role'].tolist())
            if st.button("Delete Role"):
                delete_consultant(role_to_delete)
                st.success("Deleted!")
                st.rerun()
        else:
            st.info("No consultants to delete.")

#### Step 4: Redeploy and Test the App
1. After committing the changes, wait 1-2 minutes for Streamlit to automatically update the app.
2. Open your browser and go to https://consulting-app.streamlit.app/.
3. Log in with "test"/"test".
4. Go to "New Project" and test the new styled sections and metrics.
5. Save the project and go to "Saved Projects" to see the styled results.
6. Go to "Manage Consultants" to see the improved table with alternating colors.

#### Step 5: Check if It's Finalized
1. Test all pages on your computer, tablet, and phone (resize the browser window to simulate smaller screens).
2. Make sure the app meets all requirements (calculations, saving, editing, deleting, exports, login, responsiveness).
3. If everything looks good, the project is finalized! You can share the link with your team.

If you see any errors or want to add more (e.g., a progress bar), let me know the details. Congratulations on completing the project! (It’s 1:15 PM EAT on October 20, 2025—great work!)
