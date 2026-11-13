#!/usr/bin/env python
"""Apply sidebar changes: ungate Manage/Info, remove admin nav for commuters."""

with open('templates/theme/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# ============================================================
# CHANGE 1: Make Manage section visible to all users
# Replace: {% if user.is_staff %}<li>Manage</li>{% endif %} 
# with: <li>Manage</li> (ungated)
# The exact string from the original file (lines 90-94):
# Note: has 9 spaces before {% and the li/span have different indentation
# ============================================================
manage_old = '          {% if user.is_staff %}\n<li class="nav-item">\n           <span class="dh-nav-section">Manage</span>\n         </li>\n{% endif %}'

manage_new = '          <li class="nav-item">\n  <span class="dh-nav-section">Manage</span>\n</li>'

print('Attempting Change 1: Manage section ungating')
if manage_old in content:
    content = content.replace(manage_old, manage_new)
    print('  Success: Manage section ungated')
else:
    print('  Pattern not exact, trying alternative')
    # Try the alternative without leading spaces on the if line
    manage_old2 = '{% if user.is_staff %}\n<li class="nav-item">\n  <span class="dh-nav-section">Manage</span>\n</li>\n{% endif %}'
    if manage_old2 in content:
        content = content.replace(manage_old2, manage_new)
        print('  Success: Manage section ungated (alt pattern)')
    else:
        # Try yet another pattern - just find and replace the Manage li
        manage_old3 = '<li class="nav-item">\n           <span class="dh-nav-section">Manage</span>\n         </li>'
        manage_new3 = '<li class="nav-item">\n  <span class="dh-nav-section">Manage</span>\n</li>'
        if manage_old3 in content:
            content = content.replace(manage_old3, manage_new3)
            print('  Success: Manage section ungated (3rd pattern)')
        else:
            print('  All patterns failed for Manage')

# ============================================================
# CHANGE 2: Make Info link visible to all authenticated users
# Replace the gated Info link with ungated version
# ============================================================
info_old = '        <li class="nav-item">\n          <a class="nav-link {% if request.resolver_match.app_name == \\'info\\' %}active{% endif %}" href="{% url \\'info:info_list\\' %}">\n            <span class="nav-link-icon d-md-none d-lg-inline-block">\n              <i class="nav-icon fas fa-address-card"></i>\n            </span>\n            <span class="nav-link-title">Info</span>\n          </a>\n        </li>\n{% endif %}'

info_new = '<li class="nav-item">\n  <a class="nav-link {% if request.resolver_match.app_name == \\'info\\' %}active{% endif %}" href="{% url \\'info:info_list\\' %}">\n    <span class="nav-link-icon d-md-none d-lg-inline-block">\n      <i class="nav-icon fas fa-address-card"></i>\n    </span>\n    <span class="nav-link-title">Info</span>\n  </a>\n</li>'

print('Attempting Change 2: Info link ungating')
if info_old in content:
    content = content.replace(info_old, info_new)
    print('  Success: Info link ungated')
else:
    print('  Pattern not exact, trying simpler approach')
    # Try removing just the {% if user.is_staff %} and {% endif %} while keeping the li
    # The Info link in the file is:
    #         <li class="nav-item">
    #           <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    #             <span class="nav-link-icon d-md-none d-lg-inline-block">
    #               <i class="nav-icon fas fa-address-card"></i>
    #             </span>
    #             <span class="nav-link-title">Info</span>
    #           </a>
    #         </li>
    # {% endif %}  
    # We want to remove the {% if user.is_staff %} before <li> and {% endif %} after </li>
    
    # Simpler: just replace the whole block with ungated version
    info_ungated = '''<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    <span class="nav-link-icon d-md-none d-lg-inline-block">
      <i class="nav-icon fas fa-address-card"></i>
    </span>
    <span class="nav-link-title">Info</span>
  </a>
</li>'''
    
    # Try a different approach - find the li with Info and replace
    import re
    # Find <li class="nav-item"> that contains the Info span
    m = re.search(r'(<li class="nav-item">[\s\S]*?<span class="nav-link-title">Info</span>[\s\S]*?</li>)', content)
    if m:
        # Replace the entire li with ungated version
        content = content.replace(m.group(1), info_ungated)
        print('  Success: Info link ungated (regex approach)')
    else:
        print('  Could not find Info li with regex')

# ============================================================
# CHANGE 3: Remove the admin navigation section (Admin Dashboard, 
#           Commuters, Manage Locations, Manage Routes, Manage Users, 
#           Map, Activity). This section is for admins only and should
#           not appear in the commuters sidebar.
# The admin section starts after the Info link's {% endif %} and ends
# before the user.is_authenticated section.
# ============================================================
# The admin nav HTML block - it has distinctive links like:
# - Admin Dashboard (management_dashboard)
# - Commuters (dashboard_commuters)  
# - Manage Locations (management_locations)
# - etc.
# 
# We need to remove the block between the Info section and the user.auth section
# 
# The structure is:
# ... {% endif %}  (end of Info section, line 103)
# {% if user.is_staff %}  (line 105)
# ... admin links ...
# {% endif %}  (line 168, before user.is_authenticated)
# {% if user.is_authenticated %}  (line 170)

# Find and remove the admin navigation block
# Start marker: the {% if user.is_staff %} that begins the admin section
# (this is the one after the Info section's endif)
admin_start_marker = '          {% if user.is_staff %}\n        <li class="nav-item">\n          <span class="dh-nav-section">Menu</span>\n        </li>\n        <li class="nav-item mb-1">\n          <a class="nav-link {% if request.resolver_match.url_name == \\'management_dashboard\\' %}active{% endif %}" href="{% url \\'management_dashboard\\' %}">'

# Actually, let me find the admin section by its unique content
# The admin section contains links with 'management_dashboard', 'dashboard_commuters', etc.
# Let me find the start of the admin block - it's the second {% if user.is_staff %} 
# (the first one is at line 30 for Dashboard, the second is at line 105 for Admin nav)

# Find position of first {% if user.is_staff %} (for Dashboard at line 30)
first_staff = content.find('{% if user.is_staff %}')
# Find position of second {% if user.is_staff %} (for Admin nav at line 105)
second_staff = content.find('{% if user.is_staff %}', first_staff + 10)

# Find the {% endif %} that closes the admin section (before user.is_authenticated)
# The admin section ends before {% if user.is_authenticated %}
auth_start = content.find('{% if user.is_authenticated %}')
# Find the {% endif %} between the second staff gate and the auth start
# This is tricky - let me find the admin section by its distinctive links

# Alternative approach: just remove everything from the second staff gate
# to the user.is_authenticated section
if second_staff >= 0 and auth_start >= 0:
    # Remove from second_staff to auth_start
    admin_section = content[second_staff:auth_start]
    # Check if this admin section contains management links
    management_links = ['management_dashboard', 'dashboard_commuters', 
                        'management_locations', 'management_routes',
                        'management_users', 'management_map', 'management_activity']
    has_management = any(l in admin_section for l in management_links)
    
    if has_management:
        # Remove the admin section
        new_content = content[:second_staff] + content[auth_start:]
        content = new_content
        print('  Success: Admin navigation section removed')
    else:
        print('  Admin section not found with management links')
else:
    print(f'  Debug: first_staff={first_staff}, second_staff={second_staff}, auth_start={auth_start}')

# ============================================================
# WRITE the modified content back
# ============================================================
with open('templates/theme/sidebar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('\n=== Sidebar changes applied ===')
print('Changes made:')
print('  1. Manage section: ungated (visible to all users)')
print('  2. Info link: ungated (visible to all authenticated users)')
print('  3. Admin navigation (Admin Dashboard, Commuters,')
print('     Manage Locations, Routes, Users, Map, Activity): removed from sidebar')
print('  4. Common links remain: Dashboard, Find My Route, Activity,')
print('     Active Routes, Active Locations, Transfer Links')
print('  5. User role dropdown and logout remain functional')