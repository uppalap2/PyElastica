import numpy as np

# FIXME without appending sys.path make it more generic
import sys

sys.path.append("../")

from elastica.wrappers import BaseSystemCollection, Connections, Constraints, Forcing
from elastica.rod.cosserat_rod import CosseratRod
from elastica.boundary_conditions import FreeRod
from elastica.external_forces import GravityForces
from elastica.interaction import AnistropicFrictionalPlane
from elastica.timestepper.symplectic_steppers import PositionVerlet, PEFRL
from elastica.timestepper import integrate
from FrictionValidationCases.friction_validation_postprocessing import (
    plot_friction_validation,
)


class RollingFrictionOnInclinedPlaneSimulator(
    BaseSystemCollection, Constraints, Forcing
):
    pass


# Options
PLOT_FIGURE = True
SAVE_FIGURE = True
SAVE_RESULTS = True


def simulate_rolling_friction_on_inclined_plane_with(alpha_s=0.0):

    rolling_friction_on_inclined_plane_sim = RollingFrictionOnInclinedPlaneSimulator()

    # setting up test params
    n_elem = 50
    start = np.zeros((3,))
    direction = np.array([0.0, 0.0, 1.0])
    normal = np.array([0.0, 1.0, 0.0])
    base_length = 1.0
    base_radius = 0.025
    base_area = np.pi * base_radius ** 2
    mass = 1.0
    density = mass / (base_length * base_area)
    nu = 1e-6
    E = 1e9
    # For shear modulus of 2E/3
    poisson_ratio = 0.5

    # Set shear matrix
    shear_matrix = np.repeat(1e4 * np.identity((3))[:, :, np.newaxis], n_elem, axis=2)

    shearable_rod = CosseratRod.straight_rod(
        n_elem,
        start,
        direction,
        normal,
        base_length,
        base_radius,
        density,
        nu,
        E,
        poisson_ratio,
    )

    # TODO: CosseratRod has to be able to take shear matrix as input, we should change it as done below
    shearable_rod.shear_matrix = shear_matrix

    rolling_friction_on_inclined_plane_sim.append(shearable_rod)
    rolling_friction_on_inclined_plane_sim.constrain(shearable_rod).using(FreeRod)

    gravitational_acc = -9.80665
    rolling_friction_on_inclined_plane_sim.add_forcing_to(shearable_rod).using(
        GravityForces, acc_gravity=np.array([0.0, gravitational_acc, 0.0])
    )

    alpha = alpha_s * np.pi
    origin_plane = np.array(
        [-base_radius * np.sin(alpha), -base_radius * np.cos(alpha), 0.0]
    )
    normal_plane = np.array([np.sin(alpha), np.cos(alpha), 0.0])
    normal_plane = normal_plane / np.sqrt(np.dot(normal_plane, normal_plane))
    slip_velocity_tol = 1e-4
    static_mu_array = np.array([0.4, 0.4, 0.4])  # [forward, backward, sideways]
    kinetic_mu_array = np.array([0.2, 0.2, 0.2])  # [forward, backward, sideways]

    rolling_friction_on_inclined_plane_sim.add_forcing_to(shearable_rod).using(
        AnistropicFrictionalPlane,
        k=10.0,
        nu=1e-4,
        plane_origin=origin_plane,
        plane_normal=normal_plane,
        slip_velocity_tol=slip_velocity_tol,
        static_mu_array=static_mu_array,
        kinetic_mu_array=kinetic_mu_array,
    )

    rolling_friction_on_inclined_plane_sim.finalize()
    timestepper = PositionVerlet()

    final_time = 0.5
    dt = 1e-6
    total_steps = int(final_time / dt)
    print("Total steps", total_steps)
    positions_over_time, directors_over_time, velocities_over_time = integrate(
        timestepper, rolling_friction_on_inclined_plane_sim, final_time, total_steps
    )

    # compute translational and rotational energy
    translational_energy = shearable_rod.compute_translational_energy()
    rotational_energy = shearable_rod.compute_rotational_energy()

    # compute translational and rotational energy using analytical equations
    force_slip = static_mu_array[0] * mass * gravitational_acc * np.cos(alpha)
    force_noslip = -mass * gravitational_acc * np.sin(alpha) / 3.0

    mass_moment_of_inertia = 0.5 * mass * base_radius ** 2

    if np.abs(force_noslip) <= np.abs(force_slip):
        analytical_translational_energy = (
            2.0 * mass * (gravitational_acc * final_time * np.sin(alpha)) ** 2 / 9.0
        )
        analytical_rotational_energy = (
            2.0
            * mass_moment_of_inertia
            * (gravitational_acc * final_time * np.sin(alpha) / (3 * base_radius)) ** 2
        )
    else:
        analytical_translational_energy = (
            mass
            * (
                gravitational_acc
                * final_time
                * (np.sin(alpha) - kinetic_mu_array[0] * np.cos(alpha))
            )
            ** 2
            / 2.0
        )
        analytical_rotational_energy = (
            kinetic_mu_array[0]
            * mass
            * gravitational_acc
            * base_radius
            * final_time
            * np.cos(alpha)
        ) ** 2 / (2.0 * mass_moment_of_inertia)

    return {
        "rod": shearable_rod,
        "position_history": positions_over_time,
        "velocity_history": velocities_over_time,
        "director_history": directors_over_time,
        "sweep": alpha_s,
        "translational_energy": translational_energy,
        "rotational_energy": rotational_energy,
        "analytical_translational_energy": analytical_translational_energy,
        "analytical_rotational_energy": analytical_rotational_energy,
    }


if __name__ == "__main__":
    import multiprocessing as mp

    # 0.05, 0.1, 0.2, 0.25
    # list([0.05, 0.1, 0.15, 0.2, 0.25])
    alpha_s = list([float(x) / 100.0 for x in range(5, 26, 5)])

    # across jump 0.26 0.29
    alpha_s.extend([float(x) / 100.0 for x in range(26, 30)])

    # 0.3, 0.35, ..., 0.5
    alpha_s.extend([float(x) / 100.0 for x in range(30, 51, 5)])

    with mp.Pool(mp.cpu_count()) as pool:
        results = pool.map(simulate_rolling_friction_on_inclined_plane_with, alpha_s)

    if PLOT_FIGURE:
        filename = "rolling_friction_on_inclined_plane.png"
        plot_friction_validation(results, SAVE_FIGURE, filename)

    if SAVE_RESULTS:
        import pickle

        filename = "rolling_friction_on_inclined_plane.dat"
        file = open(filename, "wb")
        pickle.dump([results], file)
        file.close()