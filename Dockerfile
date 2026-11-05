# define an alias for the specfic python version used in this file.
FROM python:3.9.12-slim-bullseye AS python

# Python build stage
FROM python AS python-build-stage

ARG BUILD_ENVIRONMENT=local
# Use reliable USTC mirror for bullseye main repo
RUN echo "deb http://mirrors.ustc.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y \
  build-essential \
  libpq-dev \
  default-libmysqlclient-dev \
  libffi-dev \
  libjpeg-dev \
  libxml2 \
  libxslt1-dev

# Requirements are installed here to ensure they will be cached.
COPY ./requirements .
# Create Python Dependency and Sub-Dependency Wheels.
RUN pip wheel --wheel-dir /usr/src/app/wheels  \
  -r ${BUILD_ENVIRONMENT}.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --extra-index-url https://pypi.org/simple

# Python 'run' stage
FROM python AS python-run-stage
LABEL title="Music Tag Web | 音乐标签网页版 (多线程高并发二开版)"
LABEL description="『音乐标签』Web版是一款可以编辑歌曲的标题，专辑，艺术家，歌词，封面等信息的应用程序"

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

# Install required system dependencies with reliable USTC mirror
RUN echo "deb http://mirrors.ustc.edu.cn/debian/ bullseye main contrib non-free" > /etc/apt/sources.list && \
    apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  gettext \
  default-libmysqlclient-dev \
  nodejs \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# copy python dependency wheels from python-build-stage
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/

# use wheels to install python dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
	&& rm -rf /wheels/

COPY ./compose/local/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# copy application code to WORKDIR
COPY . ${APP_HOME}
EXPOSE 8001
CMD ["/start"]
