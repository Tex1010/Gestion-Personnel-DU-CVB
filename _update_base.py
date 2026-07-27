with open('templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_admin = """<a href="{% url 'administration:presence_overview' %}" class="{% if request.resolver_match.url_name == 'presence_overview' and request.resolver_match.app_name == 'administration' %}is-active{% endif %}"><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>
                                <a href="{% url 'administration:settings' %}" """

new_admin = """<a href="{% url 'administration:presence_overview' %}" class="{% if request.resolver_match.url_name == 'presence_overview' and request.resolver_match.app_name == 'administration' %}is-active{% endif %}"><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>
                                <a href="{% url 'hr_events:list' %}" class="{% if request.resolver_match.app_name == 'hr_events' %}is-active{% endif %}"><i class="bi bi-heart-pulse"></i><span>Evenements RH</span></a>
                                <a href="{% url 'administration:settings' %}" """

content = content.replace(old_admin, new_admin, 1)

old_non_admin = """<a href="{% url 'administration:presence_overview' %}" class="{% if request.resolver_match.url_name == 'presence_overview' and request.resolver_match.app_name == 'administration' %}is-active{% endif %}"><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>
                            {% elif not request.user.profile.can_manage_settings %}"""

new_non_admin = """<a href="{% url 'administration:presence_overview' %}" class="{% if request.resolver_match.url_name == 'presence_overview' and request.resolver_match.app_name == 'administration' %}is-active{% endif %}"><i class="bi bi-calendar3"></i><span>Conges & absences</span></a>
                                <a href="{% url 'hr_events:list' %}" class="{% if request.resolver_match.app_name == 'hr_events' %}is-active{% endif %}"><i class="bi bi-heart-pulse"></i><span>Evenements RH</span></a>
                            {% elif not request.user.profile.can_manage_settings %}"""

content = content.replace(old_non_admin, new_non_admin, 1)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Menu items added successfully')
