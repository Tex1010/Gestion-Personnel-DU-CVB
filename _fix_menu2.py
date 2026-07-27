with open('templates/base.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

menu = '                                <a href="{% url \'hr_events:list\' %}" class="{% if request.resolver_match.app_name == \'hr_events\' %}is-active{% endif %}"><i class="bi bi-heart-pulse"></i><span>Evenements RH</span></a>\n'

new_lines = []
added = 0
for i, line in enumerate(lines):
    new_lines.append(line)
    if 'presence_overview' in line and 'calendar3' in line and 'absences' in line:
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt == '{% else %}':
                new_lines.append(menu)
                added += 1

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Menu items added:', added)
