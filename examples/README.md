# Дополнительные параметры API

`extra-body.json` — пустой корректный JSON-шаблон. Добавляйте только параметры, поддерживаемые вашим endpoint. Его содержимое попадёт в manifest и журнал запросов; секреты передавайте заголовками или переменными окружения.

Пример команды: `python3 run.py run --endpoint http://localhost:4000/v1/chat/completions --models model-a model-b --judge-model judge-model --extra-body examples/extra-body.json`.
