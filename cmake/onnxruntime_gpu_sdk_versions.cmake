include_guard(GLOBAL)

function(onnxruntime_require_native_gpu_validation component expected selected_path)
  if(CMAKE_CROSSCOMPILING OR NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR
     NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR
      "${component}: expected ${expected}; actual unverifiable; selected ${selected_path}; "
      "GPU SDK version verification requires native Linux")
  endif()
endfunction()

function(onnxruntime_check_cuda_version)
  onnxruntime_require_native_gpu_validation(
    "CUDA" "${onnxruntime_EXPECTED_CUDA_VERSION}" "${CUDAToolkit_BIN_DIR}")
  if(NOT CUDAToolkit_FOUND OR NOT CUDAToolkit_VERSION STREQUAL onnxruntime_EXPECTED_CUDA_VERSION)
    message(FATAL_ERROR
      "CUDA: expected ${onnxruntime_EXPECTED_CUDA_VERSION}; actual '${CUDAToolkit_VERSION}'; "
      "selected toolkit '${CUDAToolkit_BIN_DIR}', includes '${CUDAToolkit_INCLUDE_DIRS}'; "
      "a verifiable matching CUDAToolkit is required")
  endif()
  if(DEFINED CMAKE_CUDA_COMPILER_VERSION AND
     NOT CMAKE_CUDA_COMPILER_VERSION STREQUAL onnxruntime_EXPECTED_CUDA_VERSION)
    message(FATAL_ERROR
      "CUDA compiler: expected ${onnxruntime_EXPECTED_CUDA_VERSION}; actual '${CMAKE_CUDA_COMPILER_VERSION}'; "
      "selected compiler '${CMAKE_CUDA_COMPILER}'")
  endif()
  message(STATUS
    "CUDA: expected ${onnxruntime_EXPECTED_CUDA_VERSION}; actual ${CUDAToolkit_VERSION}; "
    "selected toolkit ${CUDAToolkit_BIN_DIR}")
endfunction()

function(onnxruntime_check_gpu_library component expected library_path header_path)
  onnxruntime_require_native_gpu_validation("${component}" "${expected}" "${library_path}")
  if(NOT IS_ABSOLUTE "${onnxruntime_GPU_VERSION_PYTHON_EXECUTABLE}" OR
     NOT EXISTS "${onnxruntime_GPU_VERSION_PYTHON_EXECUTABLE}")
    message(FATAL_ERROR
      "${component}: expected ${expected}; actual unverifiable; selected library '${library_path}', "
      "header '${header_path}'; missing recipe Python interpreter "
      "'${onnxruntime_GPU_VERSION_PYTHON_EXECUTABLE}'")
  endif()
  execute_process(
    COMMAND "${onnxruntime_GPU_VERSION_PYTHON_EXECUTABLE}"
      "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/validate_gpu_sdk.py"
      --component "${component}" --expected "${expected}"
      --library "${library_path}" --header "${header_path}"
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    RESULT_VARIABLE version_result
    OUTPUT_VARIABLE version_output
    ERROR_VARIABLE version_error
    TIMEOUT 30
  )
  if(NOT version_result STREQUAL "0")
    message(FATAL_ERROR
      "${component}: expected ${expected}; verification failed (${version_result}); "
      "selected library '${library_path}', header '${header_path}':\n"
      "${version_output}${version_error}")
  endif()
  string(STRIP "${version_output}" version_output)
  message(STATUS "${version_output}")
endfunction()
