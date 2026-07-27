import re

with open('templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# The menu item to add
menu_item = """<a href="{% url 'hr_events:list' %}" class="{% if request.resolver_match.app_name == 'hr_events' %}is-active{% endif %}"><i class="bi bi-heart-pulse"></i><span>Evenements RH</span></a>"""

# Pattern 1: In the non-admin branch (after presence_overview, before {% elif not request.user.profile.can_manage_settings %})
# The line ends with "Conges & absences</span></a>\n                            {% elif not request.user.profile.can_manage_settings %}"
pattern1 = r'(<a href="{% url \'administration:presence_overview\' %}"[^>]*><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>\n)(                            {% elif not request.user.profile.can_manage_settings %})'
replacement1 = r'\1                                ' + menu_item + '\n\2'
content = re.sub(pattern1, replacement1, content, count=1)

# Pattern 2: In the admin branch (after presence_overview, before settings link)
# The line ends with "Conges & absences</span></a>\n                                <a href="{% url 'administration:settings' %}"
pattern2 = r'(<a href="{% url \'administration:presence_overview\' %}"[^>]*><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>\n)(                                <a href="{% url \'administration:settings\' %}")'
replacement2 = r'\1                                ' + menu_item + '\n\2'
content = re.sub(pattern2, replacement2, content, count=1)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
if 'hr_events:list' in content:
    print('Menu items added successfully')
else:
    print('ERROR: Menu items not found after write')
