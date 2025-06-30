from typing import TypedDict,Dict,Any
import pandas as pd
import sys
import os
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(root_dir)
# from util.llm_factory import LLMFactory

class AgentState(TypedDict):
  employee_data: Dict[str, Any]
  gross_salary: float
  tax_deductions: float
  bonuses_deductions: float
  net_salary: float
  payslip: str
  payroll_report: Dict[str, Any]
  payment_file: str
  
  
from langgraph.graph import StateGraph,START,END
workflow = StateGraph(AgentState)

import psycopg2
from sqlalchemy import create_engine

# Fill in your PostgreSQL credentials
DB_HOST = "localhost"
DB_NAME = "employeeDb"
DB_USER = "postgres"
DB_PASS = "Koyelisha%402004"  # 🔐 Replace with actual password
DB_PORT = "5432"

# SQLAlchemy Engine for pandas
engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Load employee data into DataFrame from PostgreSQL
df = pd.read_sql("SELECT * FROM employees", engine)

# Pick one employee to test
oneEmp = df.iloc[[0]]



oneEmp = df.iloc[[0]]
from langchain_core.prompts import PromptTemplate

# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI(api_key=openai_key,model=llm_name)


def calculate_gross_salary(state: AgentState) -> AgentState:
    data = state['employee_data']
    Base_Salary = float(data['base_salary'])
    Days_Present = int(data['days_present'])
    Leaves_Taken = int(data['leaves_taken'])
    hra = float(data['house_rent_allowance'])
    sa = float(data['special_allowance'])
    lta = float(data['leave_travel_allowance'])
    # Compute Gross Salary
    gross_salary = Base_Salary * (Days_Present / (Days_Present + Leaves_Taken)) + hra + sa + lta
    # Store result
    state['gross_salary'] = round(gross_salary, 2)
    return state


def calculate_tax_deductions(state: AgentState) -> AgentState:
    data = state['employee_data']
    base_salary = float(data['base_salary'])
    tax_deduction = 0.12 * base_salary
    state['tax_deductions'] = round(tax_deduction, 2)
    return state

def calculate_bonuses_deductions(state: AgentState) -> AgentState:
    data = state['employee_data']
    performance = float(data['performance'])
    ex_gratia = float(data['bonus_ex_gratia'])
    variable_pay = float(data['variable_pay']) if performance > 3 else 0.0
    bonus_deductions = ex_gratia + variable_pay
    state['bonuses_deductions'] = round(bonus_deductions, 2)
    return state

def calculate_net_salary(state: AgentState) -> AgentState:
    gross_salary = state['gross_salary']
    tax_deductions = state['tax_deductions']
    bonuses_deductions = state['bonuses_deductions']
    print("Net Salary: ", gross_salary, ' + ', bonuses_deductions, ' - ', tax_deductions)
    net_salary = (gross_salary + bonuses_deductions) - tax_deductions
    state['net_salary'] = round(net_salary, 2)
    return state

from num2words import num2words
def amount_in_Words(amount):
    rupees = round(amount)
    paise = round((amount - rupees) * 100)
    text = f"{num2words(rupees, lang='en_IN')} rupees\n"
    if paise > 0:
        text += f"and {num2words(paise, lang='en_IN')} paise"
    text += " only"
    return text

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def save_payslip_pdf(payslip_text, emp_name, month, year):
    file_name = f"Payslip_{emp_name}_{month}_{year}.pdf"
    c = canvas.Canvas(file_name, pagesize=A4)
    width, height = A4
    c.setFont("Courier", 10)
    lines = payslip_text.strip().split('\n')
    y_position = height - inch
    for line in lines:
        c.drawString(1 * inch, y_position, line)
        y_position -= 12
        if y_position < inch:
            c.showPage()
            c.setFont("Courier", 10)
            y_position = height - inch
    c.save()
    print(f"✅ Payslip saved as: {file_name}")

def generate_payslip(state: AgentState) -> AgentState:
    data = state['employee_data']

    # Employee details
    emp_id = data['employee_id']
    emp_name = data['name']
    emp_dept = data['department']
    emp_designation = data['designation']
    emp_joining = data['date_of_joining']
    emp_pan = data['pan_no']
    emp_bank = data['bank_account_no']
    emp_uan = data['uan_no']

    # Attendance
    days_present = int(data['days_present'])
    leaves_taken = int(data['leaves_taken'])
    total_working_days = days_present + leaves_taken

    # Earnings
    base_salary = float(data['base_salary'])
    pro_rated_salary = round(base_salary * (days_present / total_working_days), 2)
    hra = round(float(data['house_rent_allowance']), 2)
    sa = round(float(data['special_allowance']), 2)
    lta = round(float(data['leave_travel_allowance']), 2)
    gross_salary = round(pro_rated_salary + hra + sa + lta, 2)

    # Deductions
    pf_fund = round(0.12 * base_salary, 2)

    # Bonuses
    variable_pay = float(data['variable_pay'])
    ex_gratia = float(data['bonus_ex_gratia'])
    bonus = state['bonuses_deductions']
    amountInWords = amount_in_Words(state['net_salary'])

    from datetime import datetime
    now = datetime.now()
    month = now.strftime("%B")
    year = now.strftime("%Y")

    payslip_template = f"""
====================================================================
                         MONTHLY PAYSLIP - {month} {year}
====================================================================

Employee Name      : {emp_name}
Employee ID        : {emp_id}
Department         : {emp_dept}
Designation        : {emp_designation}
Date of Joining    : {emp_joining}
PAN Number         : {emp_pan}
Bank Account No.   : {emp_bank}
UAN Number         : {emp_uan}

--------------------------------------------------------------------
Attendance Summary:
--------------------------------------------------------------------
Total Working Days : {total_working_days}
Days Present       : {days_present}
Leaves Taken       : {leaves_taken}

--------------------------------------------------------------------
Earnings                          Amount (INR)
--------------------------------------------------------------------
Basic Salary (Pro-rated)         :     {pro_rated_salary}
House Rent Allowance (12%)       :      {hra}
Special Allowance                :      {sa}
Leave Travel Allowance           :      {lta}
--------------------------------------------------------------------
Gross Earnings                   :     {gross_salary}

--------------------------------------------------------------------
Deductions                       Amount (INR)
--------------------------------------------------------------------
Provident Fund (12% of Basic)    :      {pf_fund}
Professional Tax                 :         0.00
TDS / Income Tax                 :         0.00
Other Deductions                 :         0.00
--------------------------------------------------------------------
Total Deductions                 :      {pf_fund}

--------------------------------------------------------------------
Bonuses & Incentives             Amount (INR)
--------------------------------------------------------------------
Performance Variable Pay         :     {variable_pay}
Bonus / Ex-Gratia                :      {ex_gratia}
--------------------------------------------------------------------
Total Incentives                 :     {bonus}
(Bonuses are provided based on the performance of the employee)

--------------------------------------------------------------------
Net Salary Summary
--------------------------------------------------------------------
Gross Earnings                   :     {state['gross_salary']}
+ Bonuses & Incentives           :     {state['bonuses_deductions']}
- Total Deductions               :      {state['tax_deductions']}
--------------------------------------------------------------------
Net Salary Payable               :     {state['net_salary']}
(In Words)                       : {amountInWords}

====================================================================
Note: This is a system-generated payslip and does not require a signature.
====================================================================
"""
    print(payslip_template)
    state['payslip'] = payslip_template
    save_payslip_pdf(payslip_template, emp_name.replace(" ", ""), month, year)
    return state


def graphCreation():
    workflow.add_node("calculate_gross_salary",calculate_gross_salary)
    workflow.add_node("calculate_tax_deductions",calculate_tax_deductions)
    workflow.add_node("calculate_bonuses_deductions",calculate_bonuses_deductions)
    workflow.add_node("calculate_net_salary",calculate_net_salary)
    workflow.add_node("generate_payslip",generate_payslip)
    
    workflow.add_edge("calculate_gross_salary","calculate_tax_deductions")
    workflow.add_edge("calculate_tax_deductions","calculate_bonuses_deductions")
    workflow.add_edge("calculate_bonuses_deductions","calculate_net_salary")
    workflow.add_edge("calculate_net_salary","generate_payslip")
    
    workflow.add_edge(START,"calculate_gross_salary")
    workflow.add_edge("generate_payslip",END)
    
    app = workflow.compile()
    from langchain_core.runnables.graph_mermaid import draw_mermaid_png
    mermaid_str = app.get_graph().draw_mermaid()
    png_bytes = draw_mermaid_png(
        mermaid_syntax=mermaid_str,
        output_file_path="graph.png",     # Path where PNG will be saved
        background_color="white",         # Optional: change as needed
        padding=20                        # Optional padding
        )
    return app
    
app = graphCreation()

# from IPython.display import Image,display

# display(
#     Image(
#         app.get_graph().draw_mermaid_png()
#     )
# )

def calculate_Employee_Salary(data:pd.DataFrame):
  data = data.to_dict(orient='records')[0]
  result = app.invoke({"employee_data":data})
  return {
      'gross_salary':result['gross_salary'],
      'tax_deductions':result['tax_deductions'],
      'bonuses_deductions':result['bonuses_deductions'],
      'net_salary':result['net_salary']
  }
  
result = calculate_Employee_Salary(oneEmp)
print('gross salary: ',result['gross_salary'])
print('tax deductions: ',result['tax_deductions'])
print('bonuses_deductions: ',result['bonuses_deductions'])
print('net salary: ',result['net_salary'])