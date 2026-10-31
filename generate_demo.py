#!/usr/bin/env python3
"""
Generate realistic HR Resume Demo assets:
- 12 professional mock resumes (PDF)
- Candidates_Database.xlsx with extracted fields
"""

from pathlib import Path
from datetime import datetime, timedelta
import random
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import pandas as pd

BASE = Path("/home/workdir/artifacts/HR_Resume_Demo")
RESUMES_DIR = BASE / "resumes"
DATA_DIR = BASE / "data"
RESUMES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Realistic candidate pool
CANDIDATES = [
    {
        "id": "C001",
        "name": "Priya Sharma",
        "email": "priya.sharma@email.com",
        "phone": "+91 98765 43210",
        "location": "Bangalore, Karnataka",
        "current_title": "Senior Software Engineer",
        "current_company": "Infosys",
        "total_experience": 6.5,
        "education": "B.Tech Computer Science - NIT Trichy (2017)",
        "skills": ["Python", "Django", "AWS", "Docker", "PostgreSQL", "REST APIs", "Git", "Agile"],
        "summary": "Experienced backend engineer with strong Python and cloud skills. Led migration of legacy systems to microservices on AWS.",
        "experience_detail": [
            ("Senior Software Engineer", "Infosys", "2021 – Present", "Led a team of 5 in building scalable REST APIs. Reduced API latency by 40%. Worked extensively with Django, AWS Lambda, and Docker."),
            ("Software Engineer", "TCS", "2017 – 2021", "Developed and maintained enterprise Java/Python applications. Implemented CI/CD pipelines.")
        ],
        "languages": "English, Hindi, Kannada"
    },
    {
        "id": "C002",
        "name": "Rahul Mehta",
        "email": "rahul.mehta@email.com",
        "phone": "+91 98123 45678",
        "location": "Pune, Maharashtra",
        "current_title": "Full Stack Developer",
        "current_company": "Cognizant",
        "total_experience": 4.0,
        "education": "B.E. Information Technology - Pune University (2020)",
        "skills": ["React", "Node.js", "TypeScript", "MongoDB", "Express", "Redux", "HTML/CSS", "Jest"],
        "summary": "Full-stack developer specializing in modern JavaScript stack. Built multiple customer-facing web applications.",
        "experience_detail": [
            ("Full Stack Developer", "Cognizant", "2021 – Present", "Developed React + Node.js applications for banking clients. Improved page load time by 35%."),
            ("Junior Developer", "Wipro", "2020 – 2021", "Worked on internal tools using React and Express.")
        ],
        "languages": "English, Hindi, Marathi"
    },
    {
        "id": "C003",
        "name": "Ananya Reddy",
        "email": "ananya.reddy@email.com",
        "phone": "+91 97654 32109",
        "location": "Hyderabad, Telangana",
        "current_title": "Data Scientist",
        "current_company": "Amazon",
        "total_experience": 5.5,
        "education": "M.Tech Data Science - IIIT Hyderabad (2019)",
        "skills": ["Python", "Machine Learning", "TensorFlow", "PyTorch", "SQL", "Pandas", "Spark", "AWS SageMaker", "NLP"],
        "summary": "Data scientist with focus on NLP and recommendation systems. Published 2 papers and deployed models serving 10M+ users.",
        "experience_detail": [
            ("Data Scientist", "Amazon", "2021 – Present", "Built recommendation models and NLP pipelines. Improved CTR by 12% using deep learning."),
            ("ML Engineer", "Flipkart", "2019 – 2021", "Developed demand forecasting models using Spark and TensorFlow.")
        ],
        "languages": "English, Telugu, Hindi"
    },
    {
        "id": "C004",
        "name": "Vikram Singh",
        "email": "vikram.singh@email.com",
        "phone": "+91 99001 12233",
        "location": "Gurgaon, Haryana",
        "current_title": "DevOps Engineer",
        "current_company": "Microsoft",
        "total_experience": 7.0,
        "education": "B.Tech Electronics - Delhi Technological University (2017)",
        "skills": ["Kubernetes", "Docker", "Terraform", "AWS", "Azure", "Jenkins", "Prometheus", "Grafana", "Linux", "Python"],
        "summary": "Senior DevOps engineer with deep expertise in container orchestration and infrastructure as code. Managed clusters serving millions of requests.",
        "experience_detail": [
            ("DevOps Engineer", "Microsoft", "2020 – Present", "Designed and maintained Kubernetes clusters on Azure. Automated infrastructure with Terraform. Reduced deployment time from hours to minutes."),
            ("System Administrator", "HCL", "2017 – 2020", "Managed Linux servers and CI/CD pipelines for enterprise clients.")
        ],
        "languages": "English, Hindi"
    },
    {
        "id": "C005",
        "name": "Sneha Patel",
        "email": "sneha.patel@email.com",
        "phone": "+91 98234 56789",
        "location": "Ahmedabad, Gujarat",
        "current_title": "UI/UX Designer",
        "current_company": "TCS",
        "total_experience": 3.5,
        "education": "B.Des Interaction Design - NID Ahmedabad (2021)",
        "skills": ["Figma", "Adobe XD", "Sketch", "User Research", "Prototyping", "Design Systems", "HTML/CSS", "Accessibility"],
        "summary": "UI/UX designer passionate about creating intuitive digital experiences. Led redesign of 3 major products increasing user satisfaction scores.",
        "experience_detail": [
            ("UI/UX Designer", "TCS", "2022 – Present", "Designed end-to-end experiences for fintech and healthcare apps. Created and maintained design systems."),
            ("Junior Designer", "Local Agency", "2021 – 2022", "Worked on mobile app designs and user research studies.")
        ],
        "languages": "English, Gujarati, Hindi"
    },
    {
        "id": "C006",
        "name": "Arjun Nair",
        "email": "arjun.nair@email.com",
        "phone": "+91 98450 11223",
        "location": "Bangalore, Karnataka",
        "current_title": "Backend Engineer",
        "current_company": "Swiggy",
        "total_experience": 5.0,
        "education": "B.Tech Computer Science - BITS Pilani (2019)",
        "skills": ["Java", "Spring Boot", "Kafka", "Redis", "MySQL", "Microservices", "AWS", "Docker"],
        "summary": "Backend engineer focused on high-throughput systems. Designed order processing services handling peak traffic of 50k RPM.",
        "experience_detail": [
            ("Backend Engineer", "Swiggy", "2021 – Present", "Built and scaled microservices for order management using Java, Kafka and Redis."),
            ("Software Developer", "Accenture", "2019 – 2021", "Developed Spring Boot services for retail clients.")
        ],
        "languages": "English, Malayalam, Hindi"
    },
    {
        "id": "C007",
        "name": "Meera Iyer",
        "email": "meera.iyer@email.com",
        "phone": "+91 98887 66554",
        "location": "Chennai, Tamil Nadu",
        "current_title": "Product Manager",
        "current_company": "Zoho",
        "total_experience": 6.0,
        "education": "MBA - IIM Bangalore (2018) | B.E. - Anna University (2015)",
        "skills": ["Product Strategy", "Roadmapping", "Agile", "User Stories", "SQL", "A/B Testing", "Jira", "Stakeholder Management"],
        "summary": "Product manager with experience taking B2B SaaS products from ideation to scale. Strong analytical and cross-functional leadership skills.",
        "experience_detail": [
            ("Product Manager", "Zoho", "2020 – Present", "Owned roadmap for CRM module. Grew active users by 2.5x through data-driven feature prioritization."),
            ("Associate Product Manager", "Freshworks", "2018 – 2020", "Worked on customer support product features and go-to-market.")
        ],
        "languages": "English, Tamil, Hindi"
    },
    {
        "id": "C008",
        "name": "Karthik Rao",
        "email": "karthik.rao@email.com",
        "phone": "+91 99112 33445",
        "location": "Bangalore, Karnataka",
        "current_title": "Machine Learning Engineer",
        "current_company": "Google",
        "total_experience": 4.5,
        "education": "M.S. Computer Science - Stanford (online) + B.Tech - IIT Madras (2019)",
        "skills": ["Python", "PyTorch", "TensorFlow", "MLOps", "Kubeflow", "Feature Stores", "SQL", "Spark", "Computer Vision"],
        "summary": "ML engineer specializing in production ML systems and computer vision. Deployed models with strict latency SLAs.",
        "experience_detail": [
            ("Machine Learning Engineer", "Google", "2022 – Present", "Built and productionized computer vision models. Implemented MLOps pipelines with Kubeflow."),
            ("ML Engineer", "Ola", "2019 – 2022", "Worked on demand prediction and pricing models.")
        ],
        "languages": "English, Kannada, Hindi"
    },
    {
        "id": "C009",
        "name": "Divya Krishnan",
        "email": "divya.krishnan@email.com",
        "phone": "+91 97777 88990",
        "location": "Kochi, Kerala",
        "current_title": "QA Automation Lead",
        "current_company": "IBM",
        "total_experience": 8.0,
        "education": "B.Tech Computer Science - CUSAT (2016)",
        "skills": ["Selenium", "Cypress", "Java", "Python", "TestNG", "API Testing", "Jenkins", "Appium", "Performance Testing"],
        "summary": "QA Automation Lead with extensive experience building test frameworks for web and mobile. Reduced regression cycle time by 60%.",
        "experience_detail": [
            ("QA Automation Lead", "IBM", "2019 – Present", "Led a team of 8 automation engineers. Built hybrid framework supporting Selenium + Cypress + Appium."),
            ("Senior QA Engineer", "Infosys", "2016 – 2019", "Automated regression suites for banking applications.")
        ],
        "languages": "English, Malayalam, Hindi"
    },
    {
        "id": "C010",
        "name": "Siddharth Joshi",
        "email": "siddharth.joshi@email.com",
        "phone": "+91 98989 00112",
        "location": "Mumbai, Maharashtra",
        "current_title": "Cloud Architect",
        "current_company": "Accenture",
        "total_experience": 9.0,
        "education": "B.E. Computer Engineering - VJTI Mumbai (2015) | AWS Certified Solutions Architect",
        "skills": ["AWS", "Azure", "GCP", "Terraform", "CloudFormation", "Kubernetes", "Serverless", "Security", "Cost Optimization", "Architecture"],
        "summary": "Cloud architect with multi-cloud expertise. Designed enterprise-scale architectures and led large migration programs.",
        "experience_detail": [
            ("Cloud Architect", "Accenture", "2019 – Present", "Architected multi-cloud solutions for Fortune 500 clients. Led AWS and Azure migrations saving 30%+ in infrastructure cost."),
            ("Senior Cloud Engineer", "Capgemini", "2015 – 2019", "Implemented infrastructure as code and CI/CD for cloud workloads.")
        ],
        "languages": "English, Hindi, Marathi"
    },
    {
        "id": "C011",
        "name": "Neha Gupta",
        "email": "neha.gupta@email.com",
        "phone": "+91 98111 22334",
        "location": "Noida, Uttar Pradesh",
        "current_title": "Frontend Engineer",
        "current_company": "Paytm",
        "total_experience": 3.0,
        "education": "B.Tech Computer Science - NSIT Delhi (2021)",
        "skills": ["React", "Next.js", "TypeScript", "Tailwind CSS", "GraphQL", "Redux Toolkit", "Jest", "Storybook"],
        "summary": "Frontend engineer focused on performant, accessible web applications. Passionate about design systems and developer experience.",
        "experience_detail": [
            ("Frontend Engineer", "Paytm", "2022 – Present", "Built high-traffic React applications. Improved Core Web Vitals scores significantly."),
            ("Junior Frontend Developer", "Startup", "2021 – 2022", "Developed component libraries and landing pages.")
        ],
        "languages": "English, Hindi"
    },
    {
        "id": "C012",
        "name": "Rohan Desai",
        "email": "rohan.desai@email.com",
        "phone": "+91 99222 33445",
        "location": "Pune, Maharashtra",
        "current_title": "Data Engineer",
        "current_company": "Jio",
        "total_experience": 5.5,
        "education": "B.Tech Information Technology - COEP Pune (2018)",
        "skills": ["Python", "Spark", "Airflow", "SQL", "Kafka", "Snowflake", "dbt", "AWS Glue", "Data Modeling"],
        "summary": "Data engineer experienced in building reliable ETL/ELT pipelines and modern data platforms. Strong focus on data quality and observability.",
        "experience_detail": [
            ("Data Engineer", "Jio", "2021 – Present", "Built data pipelines processing 100+ TB daily using Spark, Airflow and Snowflake."),
            ("Data Analyst / Engineer", "Persistent Systems", "2018 – 2021", "Developed ETL jobs and reporting solutions.")
        ],
        "languages": "English, Hindi, Marathi"
    },
]

def create_resume_pdf(candidate, output_path):
    """Generate a clean, professional-looking resume PDF."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.7*inch,
        leftMargin=0.7*inch,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=2,
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER
    )
    contact_style = ParagraphStyle(
        'ContactStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4a5568'),
        spaceAfter=8
    )
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor('#2b6cb0'),
        borderPadding=3
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY
    )
    job_title_style = ParagraphStyle(
        'JobTitle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a202c')
    )
    company_style = ParagraphStyle(
        'Company',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#4a5568')
    )
    
    story = []
    
    # Header
    story.append(Paragraph(candidate["name"], name_style))
    contact = f"{candidate['email']}  |  {candidate['phone']}  |  {candidate['location']}"
    story.append(Paragraph(contact, contact_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2b6cb0'), spaceAfter=8))
    
    # Summary
    story.append(Paragraph("PROFESSIONAL SUMMARY", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    story.append(Paragraph(candidate["summary"], body_style))
    
    # Skills
    story.append(Paragraph("TECHNICAL SKILLS", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    skills_text = " • ".join(candidate["skills"])
    story.append(Paragraph(skills_text, body_style))
    
    # Experience
    story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    
    for title, company, period, desc in candidate["experience_detail"]:
        story.append(Paragraph(f"{title}", job_title_style))
        story.append(Paragraph(f"{company}  |  {period}", company_style))
        story.append(Paragraph(desc, body_style))
        story.append(Spacer(1, 6))
    
    # Education
    story.append(Paragraph("EDUCATION", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    story.append(Paragraph(candidate["education"], body_style))
    
    # Languages
    story.append(Paragraph("LANGUAGES", section_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    story.append(Paragraph(candidate["languages"], body_style))
    
    doc.build(story)

def create_excel_database():
    """Create a professional Candidates_Database.xlsx"""
    rows = []
    for c in CANDIDATES:
        rows.append({
            "Candidate_ID": c["id"],
            "Name": c["name"],
            "Email": c["email"],
            "Phone": c["phone"],
            "Location": c["location"],
            "Current_Title": c["current_title"],
            "Current_Company": c["current_company"],
            "Total_Experience_Years": c["total_experience"],
            "Education": c["education"],
            "Key_Skills": ", ".join(c["skills"]),
            "Professional_Summary": c["summary"],
            "Resume_File": f"{c['id']}_{c['name'].replace(' ', '_')}.pdf",
            "Date_Added": (datetime.now() - timedelta(days=random.randint(5, 90))).strftime("%Y-%m-%d"),
            "Last_Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    
    df = pd.DataFrame(rows)
    
    # Write with formatting
    excel_path = DATA_DIR / "Candidates_Database.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Candidates", index=False)
        
        # Status tracking sheet (empty initially)
        status_df = pd.DataFrame(columns=[
            "Job_ID", "Job_Title", "Candidate_ID", "Candidate_Name",
            "Status", "Timestamp", "Notes", "Reviewed_By"
        ])
        status_df.to_excel(writer, sheet_name="Application_Status", index=False)
        
        # Sample Jobs sheet
        jobs = [
            {
                "Job_ID": "JOB-001",
                "Job_Title": "Senior Python Backend Engineer",
                "Department": "Engineering",
                "Location": "Bangalore / Remote",
                "Experience_Required": "4-8 years",
                "Key_Requirements": "Python, Django/Flask, AWS, Docker, REST APIs, PostgreSQL, Microservices",
                "Status": "Open",
                "Posted_Date": "2026-09-15"
            },
            {
                "Job_ID": "JOB-002",
                "Job_Title": "Machine Learning Engineer",
                "Department": "AI/ML",
                "Location": "Bangalore / Hyderabad",
                "Experience_Required": "3-6 years",
                "Key_Requirements": "Python, PyTorch/TensorFlow, MLOps, NLP or Computer Vision, SQL, Cloud (AWS/GCP)",
                "Status": "Open",
                "Posted_Date": "2026-09-20"
            },
            {
                "Job_ID": "JOB-003",
                "Job_Title": "DevOps / SRE Engineer",
                "Department": "Infrastructure",
                "Location": "Gurgaon / Bangalore",
                "Experience_Required": "5-9 years",
                "Key_Requirements": "Kubernetes, Terraform, AWS/Azure, CI/CD, Monitoring (Prometheus/Grafana), Linux",
                "Status": "Open",
                "Posted_Date": "2026-09-10"
            },
            {
                "Job_ID": "JOB-004",
                "Job_Title": "Full Stack Developer (React + Node)",
                "Department": "Engineering",
                "Location": "Pune / Bangalore",
                "Experience_Required": "3-5 years",
                "Key_Requirements": "React, Node.js, TypeScript, MongoDB/PostgreSQL, REST/GraphQL, Jest",
                "Status": "Open",
                "Posted_Date": "2026-09-25"
            },
        ]
        pd.DataFrame(jobs).to_excel(writer, sheet_name="Open_Jobs", index=False)
    
    # Basic formatting
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    wb = load_workbook(excel_path)
    
    header_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E0'),
        right=Side(style='thin', color='CBD5E0'),
        top=Side(style='thin', color='CBD5E0'),
        bottom=Side(style='thin', color='CBD5E0')
    )
    
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
        
        # Auto column width (approximate)
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 45)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        ws.row_dimensions[1].height = 22
    
    wb.save(excel_path)
    return excel_path

def main():
    print("Generating professional mock resumes and Excel database...\n")
    
    # Generate PDFs
    for c in CANDIDATES:
        filename = f"{c['id']}_{c['name'].replace(' ', '_')}.pdf"
        path = RESUMES_DIR / filename
        create_resume_pdf(c, path)
        print(f"  ✓ Created resume: {filename}")
    
    # Generate Excel
    excel_path = create_excel_database()
    print(f"\n  ✓ Created Excel database: {excel_path.name}")
    print(f"    Sheets: Candidates | Application_Status | Open_Jobs")
    
    print(f"\nDone! Assets ready in: {BASE}")
    print(f"  Resumes : {RESUMES_DIR}")
    print(f"  Data    : {DATA_DIR}")

if __name__ == "__main__":
    main()
