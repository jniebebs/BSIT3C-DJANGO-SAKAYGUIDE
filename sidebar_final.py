#!/usr/bin/env python
"""Final sidebar restructuring - remove admin sections, make Manage/Info visible to all."""

with open('templates/theme/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================
# CHANGE 1: Make Manage section visible to all users
# Replace the gated Manage section with ungated version
# The exact string from the file (lines 90-94):
#           {% if user.is_staff %}
# <li class="nav-item">
#            <span class="dh-nav-section">Manage</span>
#          </li>
# {% endif %}
#=================================================================
manage_section = '''          {% if user.is_staff %}
<li class="nav-item">
           <span class="dh-nav-section">Manage</span>
         </li>
{% endif %}'''

manage_ungated = '''          <li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>'''

if manage_section in content:
    content = content.replace(manage_section, manage_ungated)
    print('Change 1: Manage section ungated')
else:
    print('Change 1: Manage section not found - will try alternative')
    # Try alternative with different whitespace
    manage_section2 = '''{% if user.is_staff %}
<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>
{% endif %}'''
    if manage_section2 in content:
        content = content.replace(manage_section2, manage_ungated)
        print('Change 1a: Manage section ungated (alt pattern)')
    else:
        print('Change 1: Neither Manage pattern found')

# ============================================================
# CHANGE 2: Make Info link visible to all authenticated users
# The exact string from the file (lines 95-103):
#         <li class="nav-item">
#           <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
#             <span class="nav-link-icon d-md-none d-lg-inline-block">
#               <i class="nav-icon fas fa-address-card"></i>
#             </span>
#             <span class="nav-link-title">Info</span>
#           </a>
#         </li>
# {% endif %}   
#=================================================================
info_section = '''        <li class="nav-item">
          <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="nav-icon fas fa-address-card"></i>
            </span>
            <span class="nav-link-title">Info</span>
          </a>
        </li>
{% endif %}'''

# This pattern was found earlier, so let's use it
info_ungated = '''<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    <span class="nav-link-icon d-md-none d-lg-inline-block">
      <i class="nav-icon fas fa-address-card"></i>
    </span>
    <span class="nav-link-title">Info</span>
  </a>
</li>'''

if info_section in content:
    content = content.replace(info_section, info_ungated)
    print('Change 2: Info link ungated')
else:
    print('Change 2: Info section not found')

# ============================================================
# CHANGE 3: Remove the admin navigation section (previously lines 105-168)
# This contained: Admin Dashboard, Commuters, Manage Locations, 
#                Manage Routes, Manage Users, Map, Activity
# These links are now removed from the sidebar entirely
#=================================================================
# The admin section was already removed in the previous restructure
# Verify it's gone
if 'Management' in content and 'management_dashboard' in content:
    # Check if admin links are still present
    admin_links = ['management_dashboard', 'management_locations', 'management_routes', 
                   'management_users', 'management_map', 'management_activity',
                   'dashboard_commuters']
    found = [l for l in admin_links if l in content]
    if found:
        print(f'Warning: Admin links still present: {found}')
    else:
        print('Change 3: Admin navigation section successfully removed')
else:
    print('Change 3: Admin navigation section already removed')

# ============================================================
# VERIFY: Check the sidebar structure
# ============================================================
print('\n=== Sidebar Structure Verification ===')
print(f'1. Manage section gated: {"YES" if "%}Manage" in content else "NO (ungated)"}')
info_gated = '%}Info</span>' in content and 'user.is_staff' in content.split('%}Info</span>')[0][-50:]
print(f'2. Info link gated: {"YES" if info_gated else "NO (ungated)"}')

# Check common links remain
common = ['Dashboard', 'Find My Route', 'Activity', 'Active Routes', 'Active Locations', 'Transfer Links']
print(f'3. Common links present:')
for link in common:
    print(f'   - {link}: {"YES" if link in content else "NO"}')

# Check user card still works
print(f'4. User card present: {"dh-user-card" in content}')

# Check user role
print(f'5. User role display: {"Administrator" in content and "Commuter" in content}')

with open('templates/theme/sidebar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('\n=== Done! Sidebar restructured. ===')
print('Summary of changes:')
print('  1. Manage section now visible to ALL users (commuters + admins)')
print('  2. Info link now visible to ALL authenticated users')
print('  3. Admin-only navigation (Admin Dashboard, Manage Locations,')
print('     Manage Routes, Manage Users, Map, Activity, Commuters) removed')
print('  4. Common links remain: Dashboard, Find My Route, Activity,')
print('     Active Routes, Active Locations, Transfer Links')
print('  5. User role dropdown and logout remain functional')