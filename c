with open('templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Debug: check what's in the file
if "Conges & absences" in content:
    print("Found 'Conges & absences' in file")
elif "Conges & absences" in content:
    print("Found 'Conges & absences' (without amp;) in file")
else:
    print("Neither 'Conges & absences' nor 'Conges & absences' found")
    # Search for "Conges"
    idx = content.find("Conges")
    if idx >= 0:
        print(f"Found 'Conges' at index {idx}: {repr(content[idx:idx+30])}")

# Now try to add the menu items using string replacement
menu_item = "\n                                <a href=\"{% url 'hr_events:list' %}\" class=\"{% if request.resolver_match.app_name == 'hr_events' %}is-active{% endif %}\"><i class=\"bi bi-heart-pulse\"></i><span>Evenements RH</span></a>"

# Replace in non-admin branch (before {% elif not request.user.profile.can_manage_settings %})
old1 = "Conges & absences</span></a>\n                            {% elif not request.user.profile.can_manage_settings %}"
new1 = "Conges & absences</span></a>" + menu_item + "\n                            {% elif not request.user.profile.can_manage_settings %}"
if old1 in content:
    content = content.replace(old1, new1, 1)
    print("Added menu item in non-admin branch")
else:
    print("Could not find non-admin branch pattern")

# Replace in admin branch (before settings link)
old2 = "Conges & absences</span></a>\n                                <a href=\"{% url 'administration:settings' %}"
new2 = "Conges & absences</span></a>" + menu_item + "\n                                <a href=\"{% url 'administration:settings' %}"
if old2 in content:
    content = content.replace(old2, new2, 1)
    print("Added menu item in admin branch")
else:
    print("Could not find admin branch pattern")

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
count = content.count('hr_events:list')
print(f"Total hr_events:list occurrences: {count}")
