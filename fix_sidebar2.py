#!/usr/bin/env python
"""Fix the sidebar sections by matching exact content."""

with open('templates/theme/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# The exact Manage section from the file (lines 90-94)
# Note: has 9 spaces before {% and 10 spaces before </li>
manage_old = '''          {% if user.is_staff %}
<li class="nav-item">
           <span class="dh-nav-section">Manage</span>
         </li>
{% endif %}'''

manage_new = '''          <li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>'''

print('Looking for Manage pattern...')
print('Pattern starts with:', repr(manage_old[:30]))
print('In content?', manage_old in content)

# Try without the leading spaces
manage_old2 = '''{% if user.is_staff %}
<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>
{% endif %}'''

print('Pattern2 in content?', manage_old2 in content)

# Try the Info section (lines 95-103)
info_old = '''        <li class="nav-item">
          <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
            <span class="nav-link-icon d-md-none d-lg-inline-block">
              <i class="nav-icon fas fa-address-card"></i>
            </span>
            <span class="nav-link-title">Info</span>
          </a>
        </li>
{% endif %}'''

info_new = '''<li class="nav-item">
  <a class="nav-link {% if request.resolver_match.app_name == 'info' %}active{% endif %}" href="{% url 'info:info_list' %}">
    <span class="nav-link-icon d-md-none d-lg-inline-block">
      <i class="nav-icon fas fa-address-card"></i>
    </span>
    <span class="nav-link-title">Info</span>
  </a>
</li>'''

print('Looking for Info pattern...')
print('Pattern in content?', info_old in content)

# Show exact info section
lines = content.split('\n')
for i in range(93, 105):
    if i < len(lines):
        print(f'Info line {i+1}: {repr(lines[i])}')