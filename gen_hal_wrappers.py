#!/usr/bin/python
from string import Template
import CppHeaderParser



hal_impl_templ_h_file_templ = Template(\
R"""// This is generated file. Do not edit it.

#ifndef HAL_IMPL_H
#define HAL_IMPL_H

#include "hal_interface.h"

${macros_list}

// This functions can be used only in static build as inlined

#ifndef CV_HAL_INLINE
#  if defined __cplusplus
#    define CV_HAL_INLINE static inline
#  elif defined _MSC_VER
#    define CV_HAL_INLINE __inline
#  else
#    define CV_HAL_INLINE static
#  endif
#endif

//#define CV_HAL_HAS_ROUND
//CV_HAL_INLINE int cvhal_round(double val)
//{
//    // implementation
//}

#endif""")



hal_hpp_file_templ = Template(\
R"""// This is generated file. Do not edit it.

#ifndef HAL_HPP
#define HAL_HPP

#include <cstdlib>
#include <cstdio>
#include <string>
#include "core.hpp"

// OpenCV supports both dynamically-loadable and statically-linked HALs.

#if defined(CV_HAL_STATIC)
#   include "hal_impl.h"
#elif defined(CV_HAL_DYNAMIC)
#   include "hal_interface.h"
#endif

// C++ wrappers for HAL API

namespace cv { namespace hal {

// Static mode calls HAL functions directly.
// Dynamic mode calls HAL functions through pointers.

namespace detail {
    #if defined(CV_HAL_DYNAMIC)
        extern bool isInitialized;
        void initHalPointers();

    ${funcs_ptr_decl_list}
    #endif

    #if defined(CV_HAL_STATIC) || defined(CV_HAL_DYNAMIC)
        static inline CvHalMat toCvHalMat(const Mat& mat)
        {
            CvHalMat hal_mat;
            hal_mat.data = mat.data;
            hal_mat.step = mat.step;
            hal_mat.rows = mat.rows;
            hal_mat.cols = mat.cols;
            hal_mat.depth = mat.depth;
            hal_mat.channels = mat.channels;
            hal_mat.datastart = mat.data;
            hal_mat.xoff = 0;
            hal_mat.yoff = 0;
            return hal_mat;
        }

        static inline CvHalContext getContext()
        {
            CvHalContext context;
            context.opencv_version = 30;
            context.num_threads = -1;
            return context;
        }
    #endif
} // namespace detail

// All functions return true, if HAL call was successfull
// and false otherwise (for example, when HAL doesn't implement the functions).
// If HAL fails OpenCV uses own implementation.

${funcs_wrap_impl_list}

// Functions that are available only in static mode

static inline int round(double val)
{
#if defined(CV_HAL_HAS_ROUND)
    return cvhal_round(val);
#else
    // default implementation
    printf("built-in round\n");
    return cvRound(val);
#endif
}

}} // namespace cv { namespace hal {

#endif""")



func_ptr_decl_templ = Template(\
R"""        typedef CvHalStatus (*cvhal_${func_name}_func_ptr_t)(${param_hal_decl_list});
        extern cvhal_${func_name}_func_ptr_t cvhal_${func_name}_func_ptr;""")



func_wrap_code_templ = Template(\
R"""static inline bool ${func_name}(${param_ocv_decl_list})
{
#if (defined(CV_HAL_STATIC) && !defined(CV_HAL_HAS_${func_name_upper})) || (!defined(CV_HAL_STATIC) && !defined(CV_HAL_DYNAMIC))
    return false;
#else
    #if defined(CV_HAL_DYNAMIC)
        if (!detail::isInitialized)
            detail::initHalPointers();

        if (!detail::cvhal_${func_name}_func_ptr)
            return false;
    #endif

    CvHalStatus status;

${param_conversion_list}

    #if defined(CV_HAL_STATIC)
        status = cvhal_${func_name}(${param_pass_list});
    #else
        status = detail::cvhal_${func_name}_func_ptr(${param_pass_list});
    #endif

    return status == CV_HAL_SUCCESS;
#endif
}""")



hal_cpp_file_templ = Template(\
R"""// This is generated file. Do not edit it.

#include "hal.hpp"
#include <iostream>

#if defined(CV_HAL_DYNAMIC)
#   include <dlfcn.h>
#   include <pthread.h>
#endif

#if defined(CV_HAL_STATIC)

namespace
{
    // Implicit initialization

    class StaticHalInitializer
    {
    public:
        StaticHalInitializer()
        {
            std::cout << "Initialize static HAL \n" << std::endl;

            CvHalStatus status = cvhal_init();
            if (status != CV_HAL_SUCCESS)
            {
                std::cerr << "cvhal_init failed \n" << std::endl;
                return;
            }
        }
    };

    StaticHalInitializer initializer;
}

void cv::loadHalImpl(const std::string&)
{
    std::cerr << "OpenCV was built with static HAL" << std::endl;
}

std::string cv::getHalInfo()
{
    return cvhal_info();
}

#elif defined(CV_HAL_DYNAMIC)

// Pointers for dynamic mode

namespace cv { namespace hal { namespace detail {

bool isInitialized = false;
void* halLib = NULL;

typedef CvHalStatus (*cvhal_init_func_ptr_t)();
typedef const char* (*cvhal_info_func_ptr_t)();

cvhal_init_func_ptr_t cvhal_init_func_ptr = NULL;
cvhal_info_func_ptr_t cvhal_info_func_ptr = NULL;

${funcs_ptr_def_list}

}}}

void cv::loadHalImpl(const std::string& halLibName)
{
    using namespace cv::hal::detail;

    // unload previous HAL
    if (halLib)
    {
        dlclose(halLib);
        halLib = NULL;
    }

${funcs_ptr_clear_list}

    // load new HAL

    std::cout << "Initialize shared HAL : " << halLibName << "\n" << std::endl;

    halLib = dlopen(halLibName.c_str(), RTLD_NOW);
    if (!halLib)
    {
        const char* msg = dlerror();
        std::cerr << "Can't load " << halLibName << " library :" << (msg ? msg : "") << "\n" << std::endl;
        isInitialized = true;
        return;
    }

    cvhal_init_func_ptr = (cvhal_init_func_ptr_t) dlsym(halLib, "cvhal_init");
    if (!cvhal_init_func_ptr)
    {
        std::cerr << halLibName << " doesn't have cvhal_init function \n" << std::endl;
        isInitialized = true;
        return;
    }

    CvHalStatus status = cvhal_init_func_ptr();
    if (status != CV_HAL_SUCCESS)
    {
        std::cerr << "cvhal_init failed \n" << std::endl;
        isInitialized = true;
        return;
    }

    cvhal_info_func_ptr = (cvhal_info_func_ptr_t) dlsym(halLib, "cvhal_info");
    if (!cvhal_info_func_ptr)
    {
        std::cerr << halLibName << " doesn't have cvhal_info function \n" << std::endl;
        isInitialized = true;
        return;
    }

    // HAL module was loaded correctly
    // load all available functions

${funcs_load_list}

    isInitialized = true;
}

namespace
{
    pthread_once_t once_control = PTHREAD_ONCE_INIT;

    void init_routine()
    {
        // Read HAL name from enviroment variable.
        // It can be done it different ways (scan some directory,
        // config file, etc.).

        const char* halLibName = getenv("OPENCV_HAL_MODULE");
        if (!halLibName)
        {
            std::cerr << "OPENCV_HAL_MODULE env variable is empty \n" << std::endl;
            cv::hal::detail::isInitialized = true;
            return;
        }

        cv::loadHalImpl(halLibName);
    }
}

void cv::hal::detail::initHalPointers()
{
    pthread_once(&once_control, init_routine);
}

std::string cv::getHalInfo()
{
    using namespace cv::hal::detail;

    if (!isInitialized)
        initHalPointers();

    if (!cvhal_info_func_ptr)
        return "No HAL";

    return cvhal_info_func_ptr();
}

#else

void cv::loadHalImpl(const std::string&)
{
    std::cerr << "OpenCV was built without HAL support" << std::endl;
}

std::string cv::getHalInfo()
{
    return "No HAL";
}

#endif""")



class ParamInfo(object):
    def __init__(self, paramName, paramType):
        self.name = paramName
        self.halType = paramType
        if paramType == 'CvHalMat *':
            self.ocvType = 'const Mat &'
        elif paramType == 'CvHalSize':
            self.ocvType = 'Size'
        elif paramType == 'CvHalPoint':
            self.ocvType = 'Point'
        else:
            self.ocvType = paramType

    def gen_hal_decl(self):
        return self.halType + ' ' + self.name

    def gen_ocv_decl(self):
        if self.halType == 'CvHalContext *':
            return ''
        else:
            return self.ocvType + ' ' + self.name

    def gen_conversion(self):
        if self.halType == 'CvHalMat *':
            return Template('    CvHalMat hal_${param_name} = detail::toCvHalMat(${param_name});').substitute(param_name=self.name)
        elif self.halType == 'CvHalContext *':
            return '    CvHalContext context = detail::getContext();'
        else:
            return ''

    def gen_pass(self):
        if self.halType == 'CvHalMat *':
            return '&hal_' + self.name
        elif self.halType == 'CvHalContext *':
            return '&context'
        elif self.halType == 'CvHalSize':
            return '&' + self.name + '.width'
        elif self.halType == 'CvHalPoint':
            return '&' + self.name + '.x'
        else:
            return self.name



class FuncInfo(object):
    def __init__(self, name, params):
        self.fullName = name
        self.shortName = name[6:]
        self.params = params

    def gen_macros(self):
        return '//#define CV_HAL_HAS_' + self.shortName.upper()

    def gen_ptr_decl(self):
        param_hal_decl_list = []
        for param in self.params:
            param_hal_decl_list.append(param.gen_hal_decl())
        return func_ptr_decl_templ.substitute(func_name=self.shortName, param_hal_decl_list=', '.join(param_hal_decl_list))

    def gen_wrap_impl(self):
        param_ocv_decl_list=[]
        param_conversion_list = []
        param_pass_list = []
        for param in self.params:
            ocv_decl = param.gen_ocv_decl()
            if ocv_decl != '':
                param_ocv_decl_list.append(ocv_decl)
            conversion = param.gen_conversion()
            if conversion != '':
                param_conversion_list.append(conversion)
            param_pass_list.append(param.gen_pass())
        return func_wrap_code_templ.substitute(func_name=self.shortName, func_name_upper=self.shortName.upper(),
                                               param_ocv_decl_list=', '.join(param_ocv_decl_list),
                                               param_conversion_list='\n'.join(param_conversion_list),
                                               param_pass_list=', '.join(param_pass_list))

    def gen_ptr_def(self):
        return Template('${func_name}_func_ptr_t ${func_name}_func_ptr = NULL;').substitute(func_name=self.fullName)

    def gen_ptr_clear(self):
        return Template('    ${func_name}_func_ptr = NULL;').substitute(func_name=self.fullName)

    def gen_load(self):
        return Template('    ${func_name}_func_ptr = (${func_name}_func_ptr_t) dlsym(halLib, "${func_name}");').substitute(func_name=self.fullName)



class HalWrapperGenerator(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self.funcs = []

    def parse_funcs_list(self, funcs_list):
        for func in funcs_list:
            if func['rtnType'] != 'CV_HAL_API CvHalStatus':
                continue
            funcName = func['name']
            if not funcName.startswith('cvhal_'):
                continue
            if funcName == 'cvhal_init' or funcName == 'cvhal_info':
                continue
            funcParams = []
            for param in func['parameters']:
                funcParams.append(ParamInfo(param['name'], param['type']))
            self.funcs.append(FuncInfo(funcName, funcParams))

    def gen_hal_impl_templ_h_file(self):
        macros_list = []
        for func in self.funcs:
            macros_list.append(func.gen_macros())
        return hal_impl_templ_h_file_templ.substitute(macros_list='\n'.join(macros_list))

    def gen_hal_hpp_file(self):
        funcs_ptr_decl_list = []
        funcs_wrap_impl_list = []
        for func in self.funcs:
            funcs_ptr_decl_list.append(func.gen_ptr_decl())
            funcs_wrap_impl_list.append(func.gen_wrap_impl())
        return hal_hpp_file_templ.substitute(funcs_ptr_decl_list='\n\n'.join(funcs_ptr_decl_list),
                                             funcs_wrap_impl_list='\n\n'.join(funcs_wrap_impl_list))

    def gen_hal_cpp_file(self):
        funcs_ptr_def_list = []
        funcs_ptr_clear_list = []
        funcs_load_list = []
        for func in self.funcs:
            funcs_ptr_def_list.append(func.gen_ptr_def())
            funcs_ptr_clear_list.append(func.gen_ptr_clear())
            funcs_load_list.append(func.gen_load())
        return hal_cpp_file_templ.substitute(funcs_ptr_def_list='\n'.join(funcs_ptr_def_list),
                                             funcs_ptr_clear_list='\n'.join(funcs_ptr_clear_list),
                                             funcs_load_list='\n'.join(funcs_load_list))

    def gen(self):
        self.clear()

        halImplHeader = CppHeaderParser.CppHeader('hal_interface.h')
        self.parse_funcs_list(halImplHeader.functions)

        hal_impl_templ_h_file = open('hal_impl_templ.h', 'w')
        hal_impl_templ_h_file.write(self.gen_hal_impl_templ_h_file())
        hal_impl_templ_h_file.close()

        hal_hpp_file = open('hal.hpp', 'w')
        hal_hpp_file.write(self.gen_hal_hpp_file())
        hal_hpp_file.close()

        hal_cpp_file = open('hal.cpp', 'w')
        hal_cpp_file.write(self.gen_hal_cpp_file())
        hal_cpp_file.close()



if __name__ == '__main__':
    generator = HalWrapperGenerator()
    generator.gen()