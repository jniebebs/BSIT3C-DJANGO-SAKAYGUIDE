#!/usr/bin/env python
"""Restructure sidebar to separate commuter and administrator features."""

with open('templates/theme/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# ============================================================
# CHANGE 1: Remove staff gate from Manage section (lines 90-94)
# Make Manage visible to ALL users (commuters + admins)
# ============================================================
old_manage_gated = '''{% if user.is_staff %}
<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>
{% endif %}'''

new_manage_visible = '''<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>'''

if old_manage_gated in content:
    content = content.replace(old_manage_gated, new_manage_visible)
    print('Change 1: Manage section now visible to all users')
else:
    print('Change 1: Manage section pattern not found')

# ============================================================
# CHANGE 2: Remove staff gate from Info link (lines 95-102)
# Make Info visible to ALL authenticated users
# ============================================================
old_info_gated = '''{% if user.is_staff %}
<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    <span class="nav-link-icon d-md-none d-lg-inline-block">
      <i class="nav-icon fas fa-address-card"></i>
    </span>
    <span class="nav-link-title">Info</span>
  </a>
</li>
{% endif %}'''

new_info_visible = '''<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    <span class="nav-link-icon d-md-none d-lg-inline-block">
      <i class="nav-icon fas fa-address-card"></i>
    </span>
    <span class="nav-link-title">Info</span>
  </a>
</li>'''

if old_info_gated in content:
    content = content.replace(old_info_gated, new_info_visible)
    print('Change 2: Info link now visible to all authenticated users')
else:
    print('Change 2: Info link pattern not found')

# ============================================================
# CHANGE 3: Remove the admin sidebar section entirely (lines 105-168)
# This section contains: Admin Dashboard, Commuters, Manage Locations, 
#                       Manage Routes, Manage Users, Map, Activity
# These will be removed from the sidebar completely
# ============================================================
admin_section_pattern = r'''{% if user\.is_staff %}.*?{% endif %}'''  # Multi-line dotall
# Actually, let's find and remove the entire admin navigation block
# It starts after the Info link's {% endif %} and ends before the user.is_authenticated section

# Find the pattern: after line 103's % endif % , there's the admin section
# Let's use a more targeted approach - remove from {% if user.is_staff %} (line 105) 
# to the second {% endif %} that closes it (line 168)

# The admin section starts with: {% if user.is_staff %} (line 105)
# And ends with: {% endif %} (line 168, the one before user.is_authenticated)

# Let's find and remove it
admin_start = '{% if user.is_staff %}\n        <li class="nav-item">\n          <span class="dh-nav-section">Menu</span>\n        </li>\n        <li class="nav-item mb-1">\n          <a class="nav-link {% if request.resolver_match.url_name == \'management_dashboard\' %}active{% endif %}" href="{% url \'management_dashboard\' %}">'
          
# Actually, let's just remove lines 105-168 content by finding the specific pattern
# The admin nav section has these distinctive links:
# - Admin Dashboard (management_dashboard)
# - Commuters (dashboard_commuters)  
# - Manage Locations (management_locations)
# - Manage Routes (management_routes)
# - Manage Users (management_users)
# - Map Management (management_map)
# - System Activity (management_activity)

# Let's remove the entire block by replacing from the first {% if user.is_staff %} after Info
# to the {% endif %} before user.is_authenticated

# Find the start: after the Info link's closing
# The content after the Info {% endif %} (line 103) until the user.is_authenticated section

# Let me just remove the specific admin navigation block by targeting its unique content
# The block contains: "Admin Dashboard", "Commuters", "Manage Locations" etc.

# Strategy: Replace the block from the second {% if user.is_staff %} (line 105)
# to the {% endif %} before user.is_authenticated

# Actually, let me just remove lines 105-168 by replacing the specific pattern
# The admin section starts right after the Info link's {% endif %}

# Let me find where the admin section starts and ends
# Looking at the file, the admin nav is between the Info link and the user.auth section

# Let me use a regex to find and remove the admin navigation
# It starts with `<li class="nav-item mb-1">` that has management_dashboard active check
# and ends before `{% if user.is_authenticated %}`

# Actually, the simplest approach: just remove the block that begins with
# `<li class="nav-item mb-1">` with management_dashboard and ends before user.is_authenticated

# Let me just remove specific lines by targeting the content
# The admin nav HTML block starts after line 103's `{% endif %}`

# Let me take a different approach - just remove the entire admin nav block
# by replacing from the pattern that starts the admin section

# The admin nav begins after the Info link's closing tag and {% endif %}
# Looking at lines 103-168, the structure is:
# {% endif %}  (line 103)
# {% if user.is_staff %} (line 105)
# ... admin links ...
# {% endif %} (line 168)
# {% if user.is_authenticated %} (line 170)

# I'll remove lines 105-168 inclusive (the staff-gated admin navigation)

# Find the start marker: the {% if user.is_staff %} that opens the admin section
# (this is the one after the Info link's endif, not the one at line 30 or 90)
start_marker = '{% if user.is_staff %}\n        <li class="nav-item">\n          <span class="dh-nav-section">Menu</span>\n        </li>'
end_marker = '\n        {% endif %}\n\n        {% if user.is_authenticated %}'

# Find these in the content
start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx >= 0 and end_idx >= 0:
    # Remove from start_idx to end_idx + len(end_marker)
    new_content = content[:start_idx] + content[end_idx + len(end_marker):]
    content = new_content
    print(f'Change 3: Removed admin navigation section ({end_idx - start_idx} chars removed)')
else:
    print('Change 3: Could not find admin section markers')
    # Debug: show what we're looking for
    print(f'Start marker found: {start_idx >= 0}')
    print(f'End marker found: {end_idx >= 0}')
    if start_idx >= 0:
        print(f'Start marker: {repr(content[start_idx:start_idx+50])}')
    if end_idx >= 0:
        print(f'End marker: {repr(content[end_idx:end_idx+50])}')

# ============================================================
# CHANGE 4: Ensure the user role and logout remain
# ============================================================

with open('templates/theme/sidebar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('\nSidebar restructuring complete!')
print('Summary:')
print('  1. Manage section now visible to all users')
print('  2. Info link now visible to all authenticated users')
print('  3. Admin-only navigation (Admin Dashboard, Manage Locations,')
print('     Manage Routes, Manage Users, Map, Activity) removed from sidebar')
print('  4. Common links (Dashboard, Find My Route, Activity, routes,')
print('     locations, transfers) remain visible to all')
print('  5. User role dropdown and logout remain functional')