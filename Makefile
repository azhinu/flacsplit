CFLAGS += -Wall -Wextra -std=c17 -pedantic
CXXFLAGS += -Wall -Wextra -std=c++20 -pedantic
CPPFLAGS += -Ilibcuefile/include -D_XOPEN_SOURCE=500 -D_BSD_SOURCE -D_DEFAULT_SOURCE
LDFLAGS += -L/usr/local/lib
LIBS += -lFLAC++ -lboost_program_options -lboost_stacktrace_basic -licuuc -lsndfile -lFLAC -logg -lvorbis -lvorbisenc -lvorbisfile
LIBS_DYNAMIC += -lopus -lmp3lame -lid3tag -lmpg123

STATIC ?= 0
ifeq ($(STATIC),1)
LDFLAGS += -static
LINK_LIBS = $(LIBS) -Wl,-Bdynamic $(LIBS_DYNAMIC) -Wl,-Bstatic
else
LINK_LIBS = $(LIBS) $(LIBS_DYNAMIC)
endif

#CFLAGS += -g -O0
#CXXFLAGS += -g -O0

OBJS = \
	decode.o \
	encode.o \
	errors.o \
	gain_analysis.o \
	main.o \
	replaygain_writer.o \
	resample.o \
	sanitize.o \
	transcode.o \
	libcuefile.a \
	#

all: recursive-all flacsplit

recursive-all:
	@if [ ! -f libcuefile/Makefile ]; then (cd libcuefile && cmake .); fi
	@make -C libcuefile

libcuefile.a: recursive-all
	ln -sf libcuefile/src/libcuefile.a

flacsplit: $(OBJS)
	$(CXX) $(LDFLAGS) $^ $(LINK_LIBS) -o $@

decode.o: decode.cpp \
	decode.hpp \
	errors.hpp \
	transcode.hpp

encode.o: encode.cpp \
	encode.hpp \
	errors.hpp \
	replaygain_writer.hpp \
	transcode.hpp

errors.o: errors.cpp \
	errors.hpp

gain_analysis.o: \
	gain_analysis.c \
	gain_analysis.h
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

main.o: main.cpp \
	decode.hpp \
	encode.hpp \
	errors.hpp \
	gain_analysis.h \
	gain_analysis.hpp \
	replaygain_writer.hpp \
	sanitize.hpp \
	transcode.hpp

replaygain_writer.o: replaygain_writer.cpp \
	replaygain_writer.hpp

resample.o: resample.cpp \
	resample.hpp \
	transcode.hpp

sanitize.o: sanitize.cpp \
	sanitize.hpp

transcode.o: transcode.cpp \
	transcode.hpp

clean:
	rm -f $(OBJS) flacsplit

distclean: clean
	@if [ -f libcuefile/Makefile ]; then make clean -C libcuefile; fi
	find libcuefile \
	-name CMakeFiles -o \
	-name CMakeCache.txt -o \
	-name Makefile -o \
	-name cmake_install.cmake | \
    xargs rm -rf
