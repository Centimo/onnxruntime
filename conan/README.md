# Conan рецепт onnxruntime/1.21.1

### Требования

- Conan 2.x
- Образ сборки: `centimo/conan-build:1.0` (Ubuntu 24.04, gcc 13+, binutils 2.42+)
  - binutils < 2.40 не поддерживает AVX-NE-CONVERT инструкции в MLAS

---

### Зависимости (точные версии из deps.txt)

| Пакет | Версия | Примечание |
|---|---|---|
| onnx | 1.17.0 | требует `-o onnx/*:disable_static_registration=True` |
| abseil | 20240722.0 | |
| protobuf | 3.21.12 | |
| date | 3.0.1 | требует `-o date/*:use_system_tz_db=True` |
| flatbuffers | 23.5.26 | |
| safeint | 3.0.28 | |
| nlohmann_json | 3.11.3 | |
| ms-gsl | 4.0.0 | |
| nsync | 1.26.0 | только Linux |
| wil | 1.0.230629.1 | только Windows |

Зависимости без подходящей версии в Conan (eigen, re2, cpuinfo, boost/mp11) скачиваются cmake через FetchContent автоматически.

---

### Опции

| Опция | По умолчанию | Описание |
|---|---|---|
| `shared` | `False` | shared/static библиотека |
| `fPIC` | `True` | position-independent code (только Linux) |
| `with_xnnpack` | `False` | включить XNNPACK execution provider |

---

### Команда сборки

```bash
docker run --rm --network host \
  --user $(id -u):$(id -g) \
  -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro \
  -v /workspace:/workspace \
  -e CONAN_HOME=/workspace/conan-cache \
  -w /path/to/onnxruntime-1.21.1/conan \
  centimo/conan-build:1.0 \
  sh -c "conan remote disable test && conan create . --version 1.21.1 \
    -o 'onnxruntime/*:shared=False' \
    -o 'onnx/*:disable_static_registration=True' \
    -o 'date/*:use_system_tz_db=True' \
    -c 'tools.build:jobs=8' \
    --build=missing"
```

---

### Использование в проекте

```ini
# conanfile.txt
[requires]
onnxruntime/1.21.1

[generators]
CMakeDeps
CMakeToolchain
```

```cmake
find_package(onnxruntime REQUIRED)
target_link_libraries(my_target PRIVATE onnxruntime::onnxruntime)
```

---

### Известные ограничения

- Рецепт не публикуется в ConanCenter — локальное использование
- `onnx` должен быть собран с `disable_static_registration=True` (иначе конфликт статической регистрации)
- `onnx/*:shared=True` не поддерживается (link errors)
- На Windows `abseil/*:shared=True` не поддерживается (link errors)
