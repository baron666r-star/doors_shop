import json

# Читаем межкомнатные двери
with open('interior.json', 'r', encoding='utf-8') as f:
    doors = json.load(f)

# Прибавляем 1000 к каждому ID
for door in doors:
    door['id'] = int(door['id']) + 1000

# Сохраняем обратно
with open('interior.json', 'w', encoding='utf-8') as f:
    json.dump(doors, f, ensure_ascii=False, indent=4)

print("ID межкомнатных дверей успешно обновлены (теперь они начинаются с 1001)!")