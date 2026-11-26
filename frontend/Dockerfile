# Образ frontend-сервиса CYBRA.
#
# Отделён от бэкенда сознательно: это два независимых сервиса с разными
# стеками, разными циклами изменений и разными пайплайнами. Раньше SPA
# собиралась и копировалась внутрь Python-образа, из-за чего любая правка
# в вёрстке пересобирала контейнер с fastapi и torch-зависимостями.
#
# Две стадии: Node собирает статику, nginx её раздаёт. В финальном образе
# нет ни node, ни npm, ни исходников — только собранные файлы и конфиг.
# Это и размер (десятки мегабайт против гигабайта node_modules), и
# поверхность атаки: в рантайме нечего исполнять, кроме nginx.

FROM node:22-alpine AS build

WORKDIR /app

# Зависимости ставятся ДО копирования исходников: правка компонента не
# должна тянуть npm ci заново. Тот же приём, что в backend-образе с pip.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# vite.config.js пишет в ../backend/static по умолчанию — путь, который
# существует только в репозитории, где backend лежит рядом. В образе
# такой структуры нет, поэтому сборка идёт в собственный dist.
ENV CYBRA_UI_OUTDIR=/app/dist
RUN npm run build

# Проверка после сборки, а не до: пустой dist означает, что контейнер
# поднимется и будет отдавать 404 на всё. Лучше упасть здесь.
RUN test -f /app/dist/index.html \
 && echo "SPA собрана: $(du -sh /app/dist | cut -f1)"


FROM nginx:1.27-alpine AS runtime

# Дефолтный конфиг nginx раздаёт приветственную страницу на 80 порту.
# Заменяем целиком: он не знает ни про /api, ни про SPA-fallback.
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/cybra.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Непривилегированный пользователь. nginx:alpine изначально работает
# от root и слушает 80; здесь порт 8080 — он выше 1024, поэтому root для
# bind не нужен.
#
# Почему pid и temp-пути переопределены. Штатный nginx пишет pid в
# /run/nginx.pid и временные файлы в /var/cache/nginx — оба каталога
# принадлежат root, и от пользователя nginx демон падает на старте с
# `open() "/run/nginx.pid" failed (13: Permission denied)`.
#
# Первая версия правила pid через `s|pid        /var/run/nginx.pid;|...|`,
# и это не сработало: в nginx:1.27-alpine путь уже `/run/nginx.pid`, а не
# `/var/run/nginx.pid`. Шаблон не совпал, sed молча ничего не заменил,
# контейнер падал через секунду после старта — снаружи это выглядело как
# «healthcheck не отвечает», то есть диагноз приходилось искать в другом
# месте. Теперь шаблон не зависит от конкретного пути, а `nginx -t` ниже
# проверяет результат до того, как образ уедет в registry.
#
# `user nginx;` внутри конфига тоже не работает без root: nginx
# предупреждает «the "user" directive makes sense only if the master
# process runs with super-user privileges, ignored». Это безвредно, но
# строку убираем, чтобы предупреждения в логе не отвлекали от настоящих.
RUN sed -i -E 's#^pid\s+.*;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
 && sed -i -E 's#^user\s+.*;$##' /etc/nginx/nginx.conf \
 && sed -i 's|http {|http {\n    client_body_temp_path /tmp/client_temp;\n    proxy_temp_path /tmp/proxy_temp;\n    fastcgi_temp_path /tmp/fastcgi_temp;\n    uwsgi_temp_path /tmp/uwsgi_temp;\n    scgi_temp_path /tmp/scgi_temp;|' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx \
 && chmod -R a+rX /usr/share/nginx/html \
 && grep -q 'pid /tmp/nginx.pid;' /etc/nginx/nginx.conf \
 && echo "pid-файл перенесён в /tmp"

USER nginx

EXPOSE 8080

# Проверка конфига на этапе сборки, а не после выката.
#
# Тонкость: `nginx -t` от пользователя nginx открывает error_log по пути
# из конфига (/var/log/nginx/error.log), а этот каталог принадлежит root.
# Поэтому проверка идёт до переключения USER, пока права ещё есть — иначе
# валидация падала бы на правах, а не на конфиге, то есть проверяла бы не
# то, что нужно.
RUN nginx -t

# wget есть в alpine из коробки; curl — нет, а тащить его ради одной
# проверки意味着 лишний пакет в образе.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
