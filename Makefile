MTB_TYPE=COMBINED
TARGET=APP_CYSBSYSKIT-DEV-01
APPNAME=glass-radar-3rx
TOOLCHAIN=GCC_ARM
CONFIG=Release
CY_GETLIBS_SHARED_PATH=../
CY_GETLIBS_SHARED_NAME=mtb_shared
CY_IGNORE+=radar tests tools docs references recordings artifacts build
ifeq ($(RADAR_QUALIFICATION),1)
CY_IGNORE+=firmware/main.c
SOURCES+=experiments/qualification/main.c
DEFINES+=RADAR_HPF_KHZ=$(RADAR_HPF_KHZ)
DEFINES+=RADAR_SCOPE_OUTPUT=$(if $(RADAR_SCOPE_OUTPUT),$(RADAR_SCOPE_OUTPUT),0)
else
CY_IGNORE+=experiments
endif
CY_WIN_HOME=$(subst \,/,$(USERPROFILE))
CY_TOOLS_PATHS ?= $(wildcard $(CY_WIN_HOME)/ModusToolbox/tools_*)
CY_TOOLS_DIR=$(lastword $(sort $(wildcard $(CY_TOOLS_PATHS))))
include $(CY_TOOLS_DIR)/make/start.mk
