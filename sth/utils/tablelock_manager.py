import frappe
from frappe import _
from datetime import datetime

from functools import wraps

class TableLockManager:
    """Manager untuk mengelola lock status tabel"""
    
    @staticmethod
    def lock_table(doctype, duration_minutes=30, reason=""):
        """Lock tabel untuk insert"""
        key = f"table_lock:{doctype}"
        
        lock_data = {
            'locked': True,
            'locked_at': datetime.now().isoformat(),
            'locked_by': frappe.session.user,
            'duration': duration_minutes,
            'reason': reason,
            'expires_at': datetime.now().timestamp() + (duration_minutes * 60)
        }
        
        # Set di cache dengan expiry
        frappe.cache().set_value(key, lock_data, expires_in_sec=duration_minutes * 60)
        
        # Juga simpan di database untuk persistency
        # frappe.db.set_value('System Settings', 'System Settings', 
        #                    f'table_lock_{doctype}', lock_data)
        
        frappe.msgprint(_('Tabel {0} dikunci untuk insert selama {1} menit').format(
            doctype, duration_minutes))
        
        return lock_data
    
    @staticmethod
    def unlock_table(doctype):
        """Unlock tabel"""
        key = f"table_lock:{doctype}"
        
        # Hapus dari cache
        frappe.cache().delete_value(key)
        
        # Hapus dari database
        # frappe.db.set_value('System Settings', 'System Settings', 
        #                    f'table_lock_{doctype}', None)
        
        frappe.msgprint(_('Tabel {0} dibuka kembali untuk insert').format(doctype))
    
    @staticmethod
    def is_table_locked(doctype):
        """Cek apakah tabel terkunci"""
        # Cek di cache dulu (lebih cepat)
        key = f"table_lock:{doctype}"
        lock_data = frappe.cache().get_value(key)
        
        if lock_data:
            # Cek expiry
            if datetime.now().timestamp() > lock_data.get('expires_at', 0):
                frappe.cache().delete_value(key)
                return False
            return True
        
        # Fallback ke database jika cache miss
        # db_lock = frappe.db.get_value('System Settings', 'System Settings', 
        #                              f'table_lock_{doctype}')
        return False
    
    @staticmethod
    def get_lock_info(doctype):
        """Dapatkan informasi lock"""
        key = f"table_lock:{doctype}"
        return frappe.cache().get_value(key)
