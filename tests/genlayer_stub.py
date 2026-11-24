"""Minimal stand-in for the `genlayer` package.

Lets the real contract code be imported and exercised without a chain.
It mirrors only the surface the contract touches:

- ``gl.Contract`` — plain base class (storage fields are assigned by the
  test, simulating GenVM's zero-initialized storage).
- ``gl.public.write`` / ``gl.public.view`` — identity decorators.
- ``gl.vm.UserError`` — plain Exception subclass.
- ``gl.vm.run_nondet_unsafe`` — runs the leader function directly.
- ``gl.nondet.web.render`` — returns a canned page (``render_result``).
- ``gl.nondet.exec_prompt`` — returns ``prompt_result``; if that is a
  list, values are popped in order (so a test can script the verdict call
  and the reason call separately).
- ``gl.eq_principle.prompt_comparative`` / ``prompt_non_comparative`` —
  call the leader function and return its value verbatim (i.e. they
  simulate a network where every validator agrees with the leader).
- ``gl.message.sender_address`` — settable by the test.
- ``u256`` / ``u32`` / ``u64`` — int subclasses; ``Address`` — str;
  ``TreeMap`` — dict; ``DynArray`` — list.

Importing this module installs the fake ``genlayer`` package into
``sys.modules``. It must be imported BEFORE ``contract``.
"""

import sys
import types


class UserError(Exception):
    """Stand-in for gl.vm.UserError."""


class _Public:
    @staticmethod
    def write(fn):
        return fn

    @staticmethod
    def view(fn):
        return fn


class _VM:
    UserError = UserError

    @staticmethod
    def run_nondet_unsafe(leader_fn, validate_fn):
        return leader_fn()


class _Web:
    def __init__(self):
        self.render_result = ""

    def render(self, url, mode="text"):
        return self.render_result

    def get(self, url):
        raise NotImplementedError("web.get is not stubbed")


class _Nondet:
    def __init__(self):
        self.web = _Web()
        self.prompt_result = "UNVERIFIABLE"

    def exec_prompt(self, prompt, response_format=None):
        if isinstance(self.prompt_result, list):
            return self.prompt_result.pop(0)
        return self.prompt_result


class _EqPrinciple:
    @staticmethod
    def prompt_comparative(leader_fn, prompt):
        return leader_fn()

    @staticmethod
    def prompt_non_comparative(leader_fn, prompt):
        return leader_fn()


class _Message:
    sender_address = "0x0000000000000000000000000000000000000000"


class Contract:
    """Stand-in for gl.Contract."""


class TreeMap(dict):
    """Stand-in for the GenVM persistent map."""


class DynArray(list):
    """Stand-in for the GenVM persistent array."""


class u256(int):
    pass


class u32(int):
    pass


class u64(int):
    pass


Address = str

gl = types.SimpleNamespace(
    Contract=Contract,
    public=_Public(),
    vm=_VM(),
    nondet=_Nondet(),
    eq_principle=_EqPrinciple(),
    message=_Message(),
)

module = types.ModuleType("genlayer")
module.gl = gl
module.u256 = u256
module.u32 = u32
module.u64 = u64
module.Address = Address
module.TreeMap = TreeMap
module.DynArray = DynArray
module.__all__ = ["gl", "u256", "u32", "u64", "Address", "TreeMap", "DynArray"]

sys.modules["genlayer"] = module
