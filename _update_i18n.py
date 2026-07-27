with open('templates/base.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add hrEvents to the fr translations section
old_fr = '                    requestFromEmployee: "{name} a envoye une demande de {type}.",\n                },'
new_fr = '                    requestFromEmployee: "{name} a envoye une demande de {type}.",\n                    hrEvents: "Evenements RH",\n                },'
content = content.replace(old_fr, new_fr, 1)

# Add hrEvents to the en translations section
old_en = '                    requestFromEmployee: "{name} submitted a {type} request.",\n                },'
new_en = '                    requestFromEmployee: "{name} submitted a {type} request.",\n                    hrEvents: "HR Events",\n                },'
content = content.replace(old_en, new_en, 1)

# Add hrEvents to the mg translations section
old_mg = '                    requestFromEmployee: "{name} nandefa fangatahana {type}.",\n                },'
new_mg = '                    requestFromEmployee: "{name} nandefa fangatahana {type}.",\n                    hrEvents: "Hetsika Ressource Humain (RH)",\n                },'
content = content.replace(old_mg, new_mg, 1)

# Add literal translations for "Evenements RH" in en section
old_en_literal = '                    "Active l\'envoi d\'un email a l\'adresse d\'administration a chaque nouvelle demande.": "Enable sending an email to the administration address for each new request.",\n                },'
new_en_literal = '                    "Active l\'envoi d\'un email a l\'adresse d\'administration a chaque nouvelle demande.": "Enable sending an email to the administration address for each new request.",\n                    "Evenements RH": "HR Events",\n                },'
content = content.replace(old_en_literal, new_en_literal, 1)

# Add literal translations for "Evenements RH" in mg section
old_mg_literal = '                    "Active l\'envoi d\'un email a l\'adresse d\'administration a chaque nouvelle demande.": "Alefa ny mailaka any amin\'ny adiresin\'ny administrasiona isaky ny misy fangatahana vaovao.",\n                },'
new_mg_literal = '                    "Active l\'envoi d\'un email a l\'adresse d\'administration a chaque nouvelle demande.": "Alefa ny mailaka any amin\'ny adiresin\'ny administrasiona isaky ny misy fangatahana vaovao.",\n                    "Evenements RH": "Hetsika Ressource Humain (RH)",\n                },'
content = content.replace(old_mg_literal, new_mg_literal, 1)

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('i18n translations added successfully')
