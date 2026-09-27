"""P37 Neuro tasks for Isaac Lab.

Importing this package does not import Isaac Lab. The training callback calls
the register function inside an Isaac Lab Python environment.
"""

from p37_neuro_sim.isaac_tasks.registration import TASK_ID, register

__all__ = ["TASK_ID", "register"]
