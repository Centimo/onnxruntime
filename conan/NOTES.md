# Conan Recipe for onnxruntime 1.21.1 — Notes

## Цель

Создать рецепт Conan 2.x для onnxruntime 1.21.1 и разместить его в форке `Centimo/onnxruntime`
(ветка `conan-recipe-1.21`). Рецепт для локального использования, не для публикации в ConanCenter.

Конечная цель — все зависимости через Conan с точными версиями из `cmake/deps.txt`.
Первый этап — собрать хотя бы с частичным Conan + FetchContent для недостающих пакетов.

---

## Проделанная работа

### Форк и ветка
- Создан форк `Centimo/onnxruntime` на GitHub
- Добавлен remote `centimo` → `git@github.com:Centimo/onnxruntime.git`
- Создана ветка `conan-recipe-1.21`

### Структура рецепта (`conan/`)
- `conanfile.py` — рецепт Conan 2.x
- `conandata.yml` — SHA256 архива 1.21.1, маппинг onnx версии
- `patches/cmake-cxx-standard.patch` — убирает жёсткий `set(CMAKE_CXX_STANDARD)` из CMakeLists.txt

### Стратегия зависимостей

**Через Conan (точные версии из deps.txt):**
| Пакет | Версия |
|---|---|
| onnx | 1.17.0 |
| abseil | 20240722.0 |
| protobuf | 3.21.12 |
| date | 3.0.1 |
| flatbuffers | 23.5.26 |
| safeint | 3.0.28 |
| nlohmann_json | 3.11.3 |
| ms-gsl | 4.0.0 |
| nsync | 1.26.0 (Linux) |
| wil | 1.0.230629.1 (Windows) |

**Через FetchContent (нет точной версии в Conan):**
| Пакет | Причина |
|---|---|
| eigen | коммит `1d8b82b` (между 3.4 и 5.0, нет в Conan) |
| re2 | версия `2024-07-02` отсутствует в Conan |
| cpuinfo | коммит `8a1772a` отсутствует в Conan |
| boost/mp11 | коммит `boost-1.82.0` — берётся напрямую |

Оригинальный `cmake/external/onnxruntime_external_deps.cmake` используется без замены —
он сам применяет `FIND_PACKAGE_ARGS` и находит Conan-пакеты через `find_package`,
а для остальных делает FetchContent.

---

## Решённые проблемы

| Проблема | Решение |
|---|---|
| `test` remote (localhost:1) блокирует резолвинг | `conan remote disable test` перед запуском |
| `date/3.0.1` тянет `libcurl` через `tz_db=download` | `-o 'date/*:use_system_tz_db=True'` при сборке; `default_options` в рецепте |
| `cmake/4.2.3` тянет `libcurl/8.18.0` (несовместим с Conan 2.19) | `cmake/[>=3.28 <4]` в `build_requirements` |
| Патч `cmake-cxx-standard.patch` не парсится `patch_ng` | Пустые контекстные строки требуют пробела (` \n`), не просто `\n`; счётчики hunk должны быть точными |
| Eigen SHA1 хэш устарел (GitLab перегенерирует архивы) | `replace_in_file` убирает `URL_HASH SHA1=${DEP_SHA1_eigen}` из `eigen.cmake` |
| При использовании abseil через Conan include-директории не добавляются глобально | `replace_in_file` в `abseil-cpp.cmake` добавляет `include_directories(${absl_INCLUDE_DIRS})` когда abseil из `find_package` |
| `cvtfp16Avx.S` — инструкции AVX-NE-CONVERT (`vcvtneeph2ps`) не поддерживаются binutils 2.38 | Новый образ `centimo/conan-build:1.0` (Ubuntu 24.04) с binutils 2.42 |
| `cmake/4.x` тянул `libcurl` несовместимый с Conan 2.19; убрали `tool_requires("cmake/...")` | cmake 3.31 из pip уже в образе, Conan находит его автоматически |
| FetchContent скачивал eigen/re2/cpuinfo заново при каждом `conan remove` | `FETCHCONTENT_BASE_DIR=/workspace/conan-cache/fetchcontent` — постоянное место вне build-dir |

---

## Текущий статус

**Сборка успешна.** Пакет создан в Conan-кэше:
```
onnxruntime/1.21.1#e69b92198209877e2023bdd3e928d115:f2478c4b0a0ec6f5b87c01ea9bf60fd522db3344#7c856c8b97724207507bee957ccc8233
```
10 `.a` файлов + `libonnxruntime_providers_shared.so` + 89 заголовков.

Образ для сборки: `centimo/conan-build:1.0` (Ubuntu 24.04, gcc 13.3, binutils 2.42).
`centimo/full:1.2` не подходит — в нём binutils 2.38 не поддерживает AVX-NE-CONVERT инструкции из `cvtfp16Avx.S`.

---

## Следующие шаги

1. Закоммитить финальный рецепт
2. Запушить в `centimo/conan-recipe-1.21`
3. Второй этап: добавить Conan-пакеты для недостающих зависимостей (eigen, re2, cpuinfo)

---

## Команда для сборки

```bash
docker run --rm --network host \
  --user $(id -u):$(id -g) \
  -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro \
  -v /workspace:/workspace \
  -e CONAN_HOME=/workspace/conan-cache \
  -w /workspace/projects/Cpp/onnxruntime-1.21.1/conan \
  centimo/conan-build:1.0 \
  sh -c "conan remote disable test && conan create . --version 1.21.1 \
    -o 'onnxruntime/*:shared=False' \
    -o 'onnx/*:disable_static_registration=True' \
    -o 'date/*:use_system_tz_db=True' \
    -c 'tools.build:jobs=8' \
    --build=missing"
```

Образ `centimo/conan-build:1.0` — Ubuntu 24.04, gcc 13.3, binutils 2.42, conan 2.19, cmake 3.31.
Dockerfile: `/workspace/projects/devops/conan/Dockerfile.conan-build`
Заменяет `centimo/full:1.2` для сборки onnxruntime (binutils 2.42 нужен для AVX-NE-CONVERT).
