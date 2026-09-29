"""Omega Runtime Host & Plugin Engine for Two Agents, One Truth."""

import os
import sys
import importlib
from hyperon import MeTTa
from hyperon.atoms import OperationAtom, ValueAtom

class OmegaRuntime:
    """Simulates an Omega Agent Runtime host.
    
    Loads plugins, registers skill definitions in MeTTa, bridges python calls,
    and executes symbolic agent skills.
    """

    def __init__(self, plugins_dir: str = None):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.app_dir = os.path.join(self.repo_root)
        self.plugins_dir = plugins_dir or os.path.join(self.app_dir, "omega", "plugins")

        os.environ["TWOAGENTS_HOME"] = self.app_dir
        if self.app_dir not in sys.path:
            sys.path.insert(0, self.app_dir)

        self.skills = {}
        self.metta = MeTTa()
        self._register_builtins()
        self._load_plugins()

    def _register_builtins(self):
        """Register built-in Omega MeTTa operations: add-skill and py-call."""
        def add_skill_op(name_atom, desc_atom, spec_atom=None):
            skill_name = str(name_atom).strip('"')
            desc = str(desc_atom).strip('"')
            spec = str(spec_atom).strip('"') if spec_atom else "arg"
            self.skills[skill_name] = {
                "name": skill_name,
                "description": desc,
                "spec": spec,
                "status": "registered"
            }
            return [ValueAtom(f"skill:{skill_name}")]

        def py_call_op(call_expr):
            children = call_expr.get_children()
            if not children:
                return [ValueAtom("error: empty py-call")]
            func_sym = str(children[0])
            args = [str(arg).strip('"') for arg in children[1:]]

            mod_name, func_name = func_sym.split(".")
            # Ensure plugin directory is in sys.path for bridge modules
            plugin_subdirs = [os.path.join(self.plugins_dir, d) for d in os.listdir(self.plugins_dir) if os.path.isdir(os.path.join(self.plugins_dir, d))]
            for pdir in plugin_subdirs:
                if pdir not in sys.path:
                    sys.path.insert(0, pdir)

            mod = importlib.import_module(mod_name)
            func = getattr(mod, func_name)
            res = func(*args)
            return [ValueAtom(res)]

        self.metta.register_atom("add-skill", OperationAtom("add-skill", add_skill_op, unwrap=False))
        self.metta.register_atom("py-call", OperationAtom("py-call", py_call_op, unwrap=False))

    def _load_plugins(self):
        """Scan plugins directory, load plugin .metta files, and execute (loadOmegaPlugin)."""
        if not os.path.exists(self.plugins_dir):
            return

        for entry in sorted(os.listdir(self.plugins_dir)):
            plugin_folder = os.path.join(self.plugins_dir, entry)
            if os.path.isdir(plugin_folder):
                if plugin_folder not in sys.path:
                    sys.path.insert(0, plugin_folder)
                for file in sorted(os.listdir(plugin_folder)):
                    if file.endswith(".metta"):
                        metta_path = os.path.join(plugin_folder, file)
                        with open(metta_path, "r", encoding="utf-8") as f:
                            code = f.read()
                        self.metta.run(code)

        # Trigger plugin initialization hook
        self.metta.run("!(loadOmegaPlugin)")

    def list_skills(self):
        """Return all skills registered in Omega runtime."""
        return list(self.skills.values())

    def invoke_skill(self, skill_name: str, argument: str) -> str:
        """Invoke a registered skill via Omega MeTTa runtime."""
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' is not registered in Omega runtime.")
        
        # Clean argument for MeTTa string literal
        safe_arg = str(argument).replace('\\', '\\\\').replace('"', '\\"')
        query = f'!({skill_name} "{safe_arg}")'
        result_atoms = self.metta.run(query)

        if result_atoms and result_atoms[0]:
            raw_res = str(result_atoms[0][0])
            return raw_res.strip('"')
        return "No response from skill execution"


# Global singleton instance for app runtime
runtime = OmegaRuntime()
