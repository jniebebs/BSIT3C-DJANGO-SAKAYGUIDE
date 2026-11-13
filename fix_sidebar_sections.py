#!/usr/bin/env python
"""Fix the Manage and Info sections in the sidebar."""

with open('templates/theme/sidebar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Make Manage section visible to all (remove {% if user.is_staff %} gate)
manage_old = '''{% if user.is_staff %}
<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>
{% endif %}'''

manage_new = '''<li class="nav-item">
  <span class="dh-nav-section">Manage</span>
</li>'''

if manage_old in content:
    content = content.replace(manage_old, manage_new)
    print('Fix 1: Manage section now visible to all')
else:
    print('Fix 1: Manage section pattern not found')

# Fix 2: Make Info link visible to all authenticated users
info_old = '''{% if user.is_staff %}
<li class="nav-item">
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

if info_old in content:
    content = content.replace(info_old, info_new)
    print('Fix 2: Info link now visible to all authenticated users')
else:
    print('Fix 2: Info link pattern not found')

with open('templates/theme/sidebar.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('\nSidebar fixes complete!')