import frappe
from frappe import _
import calendar
from datetime import datetime

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    """Generate dynamic columns based on selected month"""
    columns = [
        {
            "fieldname": "employee_name",
            "label": _("Nama"),
            "fieldtype": "Data",
            "width": 200,
            "align": "left"
        }
    ]
    
    bulan = filters.get("bulan")
    tahun = filters.get("tahun")
    
    month_map = {
        "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
        "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
        "September": 9, "Oktober": 10, "November": 11, "Desember": 12
    }
    
    month_num = month_map.get(bulan, 1)
    num_days = calendar.monthrange(int(tahun), month_num)[1]
    
    for day in range(1, num_days + 1):
        columns.append({
            "fieldname": f"day_{day}",
            "label": str(day),
            "fieldtype": "Data",
            "width": 43,
            "align": "center"
        })
    
    summary_cols = [
        {"fieldname": "hke", "label": "HKE", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "mg", "label": "MG", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "p1", "label": "P1", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "p2", "label": "P2", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "s1", "label": "S1", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "s2", "label": "S2", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "c", "label": "C", "fieldtype": "Data", "width": 55, "align":"center"},
        {"fieldname": "m", "label": "M", "fieldtype": "Data", "width": 55, "align":"center"}
    ]
    
    columns.extend(summary_cols)
    return columns

def get_data(filters):
    """Get attendance data for all employees"""
    bulan = filters.get("bulan")
    tahun = filters.get("tahun")
    
    month_map = {
        "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
        "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
        "September": 9, "Oktober": 10, "November": 11, "Desember": 12
    }
    
    month_num = month_map.get(bulan, 1)
    year = int(tahun)
    num_days = calendar.monthrange(year, month_num)[1]
    
    employees = frappe.get_all("Employee", 
        filters={"status": "Active"},
        fields=["name", "employee_name"],
        order_by="employee_name"
    )
    
    data = []
    
    for emp in employees:
        row = {
            "employee_name": emp.employee_name,
            "hke": 0,
            "mg": 0,
            "p1": 0,
            "p2": 0,
            "s1": 0,
            "s2": 0,
            "c": 0,
            "m": 0
        }
        
        attendances = frappe.get_all("Attendance",
            filters={
                "employee": emp.name,
                "attendance_date": ["between", [
                    f"{year}-{month_num:02d}-01",
                    f"{year}-{month_num:02d}-{num_days:02d}"
                ]]
            },
            fields=["attendance_date", "status", "leave_type", "status_code"]
        )
        
        attendance_dict = {}
        for att in attendances:
            day = att.attendance_date.day
            attendance_dict[day] = att
        
        for day in range(1, num_days + 1):
            date_obj = datetime(year, month_num, day)
            day_of_week = date_obj.weekday()
            
            status = ""
            
            if day_of_week == 6: 
                status = "MG"
                row["mg"] += 1
            elif day in attendance_dict:
                att = attendance_dict[day]
                if att.status_code == "S":
                    status = "S"
                    row["s1"] += 1
                elif att.status_code == "P1":
                    status = "P1"
                    row["p1"] += 1
                elif att.status_code == "P2":
                    status = "P2"
                    row["p2"] += 1
                elif att.status_code == "C":
                    status = "C"
                    row["c"] += 1
                elif att.status_code == "M":
                    status = "M"
                    row["m"] += 1
                elif att.status_code == "H":
                    status = "H"
                    row["hke"] += 1
            
            row[f"day_{day}"] = status
        
        data.append(row)
    
    return data