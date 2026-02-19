"""
src/extraction/ffi_wrapper.py

The FFI Bridge: Python <-> Verified Native Code.

This module implements the runtime binding layer described in Section 4.3.
It allows the Python application (e.g., the Speculative Stream Processor) to
invoke the formally verified logic compiled from Lean 4.

Key Responsibilities:
1. Load the shared library (.so/.dylib).
2. Initialize the Lean runtime and the specific module.
3. Expose a Pythonic interface to the raw C symbols (exported via @[export]).
"""

import ctypes
import logging
import sys
import os
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger("LMGPA.FFI")

class VerifiedModule:
    """
    A wrapper around a dynamically loaded verified artifact.
    """

    def __init__(self, lib_path: Path, module_name: str = "Main"):
        """
        Args:
            lib_path: Path to the .so/.dylib file.
            module_name: The Lean module name (used for initialization).
        """
        self.lib_path = lib_path
        self.module_name = module_name
        self._lib = None
        
        if not lib_path.exists():
            raise FileNotFoundError(f"Shared library not found at: {lib_path}")

        try:
            self._load_library()
            self._initialize_lean_runtime()
        except Exception as e:
            logger.critical(f"Failed to initialize verified module: {e}")
            raise

    def _load_library(self):
        """Loads the shared object using ctypes."""
        logger.info(f"Loading shared library: {self.lib_path}")
        # RTLD_GLOBAL is often needed for Lean's symbol resolution
        mode = ctypes.RTLD_GLOBAL if sys.platform != "win32" else 0
        self._lib = ctypes.CDLL(str(self.lib_path), mode=mode)

    def _initialize_lean_runtime(self):
        """
        Bootstraps the Lean 4 runtime. 
        Crucial step: calling compiled Lean code without this will segfault.
        """
        logger.debug("Initializing Lean 4 Runtime...")
        
        # 1. Initialize the generic Lean runtime
        # void lean_initialize_runtime_module();
        if hasattr(self._lib, "lean_initialize_runtime_module"):
             self._lib.lean_initialize_runtime_module()
        
        # void lean_initialize();
        if hasattr(self._lib, "lean_initialize"):
            self._lib.lean_initialize()

        # void lean_io_mark_end_initialization();
        if hasattr(self._lib, "lean_io_mark_end_initialization"):
            self._lib.lean_io_mark_end_initialization()

        # 2. Initialize the specific module
        # The naming convention is usually `initialize_<ModuleName>`
        # e.g., initialize_Main or initialize_StreamSpec
        init_sym_name = f"initialize_{self.module_name}"
        
        # Handle simple name mangling if necessary (often just `initialize_...`)
        if hasattr(self._lib, init_sym_name):
            init_func = getattr(self._lib, init_sym_name)
            # Init functions typically return a lean_object* (IO Unit), which we can ignore or check
            init_func.restype = ctypes.c_void_p
            init_func.argtypes = [ctypes.c_void_p] # accept a 'res' arg usually, or none depending on version
            
            # For simplicity in prototype, we assume the standard 0-arg or 1-arg init
            try:
                # Modern Lean module init often takes 1 arg (builtin_init) or 0.
                # We try 0 first.
                init_func()
                logger.info(f"Module '{self.module_name}' initialized successfully.")
            except TypeError:
                # Fallback
                logger.warning("Initialization might require arguments. Skipping for prototype safety.")
        else:
            logger.warning(f"Initialization symbol '{init_sym_name}' not found. Logic might fail.")

    def get_function(self, symbol_name: str, arg_types: List[Any], res_type: Any):
        """
        Retrieves a raw C function handle from the library.
        
        Args:
            symbol_name: The C symbol name (must match @[export name] in Lean).
            arg_types: List of ctypes types (e.g., [ctypes.c_uint32]).
            res_type: Return type (e.g., ctypes.c_bool).
        """
        if not hasattr(self._lib, symbol_name):
            raise AttributeError(f"Symbol '{symbol_name}' not found in library.")
        
        func = getattr(self._lib, symbol_name)
        func.argtypes = arg_types
        func.restype = res_type
        return func

class StreamProcessorWrapper(VerifiedModule):
    """
    Concrete wrapper for the Speculative Stream Processor (Benchmark 01).
    Exposes a Pythonic API on top of the FFI.
    """
    
    def __init__(self, lib_path: Path):
        super().__init__(lib_path, module_name="Main")
        
        # Bind the core processing function
        # Corresponds to Lean: @[export stream_process] def process ...
        self._process = self.get_function(
            "stream_process",
            [ctypes.c_uint64, ctypes.c_uint64], # e.g., (state_id, event_id)
            ctypes.c_uint64                     # returns new_state_id
        )

    def process_event(self, state_id: int, event_id: int) -> int:
        """
        Invokes the verified logic. 
        Guaranteed to be race-free by the Formal-SDD construction.
        """
        return self._process(state_id, event_id)