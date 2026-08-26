// Workaround to a bug in libstdc++ prior to GCC 11 causing
// Error: attempt to self move assign.
// when compiling with _GLIBCXX_DEBUG
// see https://gcc.gnu.org/bugzilla/show_bug.cgi?id=85828
#if defined(_GLIBCXX_DEBUG) && defined(__GNUC__) && (__GNUC__ < 11)
#include <debug/macros.h>
#undef __glibcxx_check_self_move_assign
#define __glibcxx_check_self_move_assign(x)
#ifdef __glibcxx_check_self_move_assign // suppress unused macro warning
#endif
#endif

// Common to all build targets
#include <algorithm>
#include <array>
#include <bitset>
#include <cassert>
#include <cctype>
#include <cerrno>
#include <cfenv>
#include <cfloat>
#include <chrono>
#include <cinttypes>
#include <climits>
#include <clocale>
#include <cmath>
#include <codecvt>
#include <complex>
#include <csetjmp>
#include <csignal>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <cuchar>
#include <cwchar>
#include <cwctype>
#include <deque>
#include <exception>
#include <filesystem>
#include <forward_list>
#include <fstream>
#include <functional>
#include <initializer_list>
#include <iomanip>
#include <ios>
#include <iosfwd>
#include <iostream>
#include <istream>
#include <iterator>
#include <limits>
#include <list>
#include <locale>
#include <map>
#include <memory>
#include <mutex>
#include <new>
#include <numeric>
#include <optional>
#include <ostream>
#include <queue>
#include <random>
#include <ratio>
#include <regex>
#include <scoped_allocator>
#include <set>
#include <sstream>
#include <stack>
#include <stdexcept>
#include <streambuf>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <tuple>
#include <type_traits>
#include <typeindex>
#include <typeinfo>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
#include <flatbuffers/flexbuffers.h>

// The vehicle-editor toolbar currently uses std::string::starts_with-style syntax,
// while Cataclysm's supported build mode is C++17.  Keep those expressions
// source-compatible until the toolbar call sites are rewritten to the project's
// C++17 prefix idiom.  This macro is only active where the standard library does
// not provide starts_with itself.
#if !defined(__cpp_lib_starts_ends_with)
#define starts_with(prefix) rfind( ( prefix ), 0 ) == 0
#endif

#if defined(_MSC_VER)
#   include "platform_win.h"
#endif

#if defined(TILES)
#   include <sdl_wrappers.h>
#endif