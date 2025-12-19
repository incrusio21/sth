import frappe

def create_user_permission(self,method):
    if not self.user_id:
        return

    for row in self.job:
        pass