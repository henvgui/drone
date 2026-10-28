"""Recompute ESC V1 planning estimates with Python's standard library.

All current predictions are scenarios, not measured propeller performance.
Input, phase-loop and gate currents are deliberately kept separate.
Run from any directory: python tools/esc_budget.py
"""

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def induced_power(thrust_n, area_m2, density):
    return thrust_n ** 1.5 / math.sqrt(2 * density * area_m2)


def calculate(p):
    n = p["motor_count"]
    area = math.pi * (p["prop_diameter_in"] * 0.0254 / 2) ** 2
    mass = {
        field: sum(item[field + "_g"] for item in p["mass_items"])
        for field in ("low", "nominal", "high")
    }
    scenarios = []
    for mass_g in p["mass_scenarios_g"]:
        for ratio in p["thrust_ratios"]:
            thrust_g = mass_g * ratio / n
            ideal_w = induced_power(
                thrust_g / 1000 * p["gravity_m_s2"], area,
                p["air_density_kg_m3"],
            )
            motor_w_low = ideal_w * p["installation_power_factor"] / p["electrical_induced_efficiency_high"]
            motor_w_high = ideal_w * p["installation_power_factor"] / p["electrical_induced_efficiency_low"]
            scenarios.append({
                "mass_g": mass_g, "total_thrust_to_weight": ratio,
                "thrust_per_motor_gf": thrust_g,
                "ideal_induced_power_per_motor_w": ideal_w,
                "input_current_per_motor_11_4v_a": [motor_w_low / p["voltage_nominal_v"], motor_w_high / p["voltage_nominal_v"]],
                "input_current_per_motor_10_5v_a": [motor_w_low / p["voltage_current_budget_v"], motor_w_high / p["voltage_current_budget_v"]],
                "total_battery_current_10_5v_a": [(n * motor_w_low + p["auxiliary_power_w"]) / p["voltage_current_budget_v"], (n * motor_w_high + p["auxiliary_power_w"]) / p["voltage_current_budget_v"]],
                "not_a_prediction_of_available_maximum_thrust": True,
            })

    ref = p["reference_bench"]
    ref_area = math.pi * (ref["diameter_in"] * 0.0254 / 2) ** 2
    ref_pi = induced_power(ref["thrust_g"] / 1000 * p["gravity_m_s2"], ref_area, p["air_density_kg_m3"])
    pcb = p["esc_pcb_estimate"]
    pcb_area = pcb["width_mm"] * pcb["height_mm"]
    cu_thickness = sum(pcb["copper_layer_thickness_mm"])
    retained_cu_thickness = cu_thickness * pcb["average_copper_coverage"]
    pcb_fr4 = pcb_area * (pcb["finished_thickness_mm"] - retained_cu_thickness) / 1000 * pcb["fr4_density_g_cm3"]
    pcb_copper = pcb_area * cu_thickness * pcb["average_copper_coverage"] / 1000 * pcb["copper_density_g_cm3"]

    wires = []
    wire = p["wire"]
    for section in wire["sections"]:
        length = section["total_conductor_length_m"]
        copper_g = section["area_mm2"] * length * wire["copper_density_g_cm3"]
        jacket_area = math.pi * section["outer_diameter_mm"] ** 2 / 4 - section["area_mm2"]
        jacket_g = jacket_area * length * wire["insulation_density_g_cm3"]
        wires.append({"name": section["name"], "copper_mass_g": copper_g,
                      "insulation_mass_g": jacket_g, "total_mass_g": copper_g + jacket_g})

    fet = p["mosfet"]
    bridge = []
    for current in fet["current_loop_rms_scenarios_a"]:
        conduction = 2 * current ** 2 * fet["hot_rds_on_budget_ohm"]
        switching = (0.5 * p["voltage_full_v"] * current * fet["switching_transition_sum_s"]
                     * fet["pwm_hz"] * fet["hard_switching_devices_per_period"])
        deadtime = 2 * current * fet["diode_drop_budget_v"] * fet["effective_deadtime_s"] * fet["pwm_hz"]
        bridge.append({
            "conducting_loop_rms_a": current, "bridge_conduction_loss_w": conduction,
            "bridge_switching_loss_w": switching, "bridge_deadtime_loss_w": deadtime,
            "bridge_loss_budget_w": conduction + switching + deadtime + fet["additional_bridge_loss_allowance_w"],
            "shunt_loss_if_shunt_rms_equals_loop_rms_w": current ** 2 * fet["shunt_ohm"],
            "shunt_voltage_magnitude_v": current * fet["shunt_ohm"],
        })

    wire_checks = []
    for name, area_mm2, loop_length_m, currents in [
        ("AWG20 ESC DC branch", 0.518, 0.2, [10, 20]),
        ("AWG16 main DC loop", 1.31, 0.2, [15, 20, 40]),
        ("AWG24 original two active motor leads, phase current", 0.205, 0.3, [10, 20]),
        ("AWG24 shortened two active motor leads, phase current", 0.205, 0.1, [10, 20]),
    ]:
        r20 = wire["copper_resistivity_ohm_mm2_m"] * loop_length_m / area_mm2
        r75 = r20 * (1 + wire["copper_temperature_coefficient_per_k"] * 55)
        wire_checks.append({"name": name, "resistance_20c_ohm": r20, "resistance_75c_ohm": r75,
                            "currents": [{"a": i, "drop_75c_v": i * r75, "loss_75c_w": i ** 2 * r75} for i in currents]})

    return {
        "revision": p["revision"], "mass_totals_g": mass, "rotor_disk_area_m2": area,
        "reference_point_ideal_induced_power_w": ref_pi,
        "reference_point_ideal_induced_to_electrical_power_ratio": ref_pi / ref["reported_input_power_w"],
        "performance_scenarios": scenarios,
        "pcb_estimate_g": {"fr4": pcb_fr4, "retained_copper": pcb_copper,
                           "assembled": pcb_fr4 + pcb_copper + pcb["components_and_solder_g"]},
        "wire_mass_estimates": wires, "wire_mass_total_g": sum(x["total_mass_g"] for x in wires),
        "bridge_loss_scenarios": bridge,
        "gate_driver": {
            "all_six_gate_average_current_24khz_a": 6 * fet["qg_design_budget_c"] * fet["pwm_hz"],
            "all_three_high_side_average_current_24khz_a": 3 * fet["qg_design_budget_c"] * fet["pwm_hz"],
            "all_three_high_side_average_current_48khz_a": 3 * fet["qg_design_budget_c"] * 48000,
            "gate_charge_power_24khz_w": 6 * fet["qg_design_budget_c"] * fet["pwm_hz"] * fet["gate_voltage_budget_v"],
            "miller_charge_time_source_s": fet["qgd_datasheet_max_c"] / fet["driver_source_current_a"],
            "miller_charge_time_sink_s": fet["qgd_datasheet_max_c"] / fet["driver_sink_current_a"],
        },
        "wire_electrical_checks": wire_checks,
        "battery_label_only": {"nominal_energy_wh": 1.1 * 11.4,
                               "manufacturer_60c_current_a": 1.1 * 60,
                               "specific_energy_at_user_66g_wh_kg": 1.1 * 11.4 / 0.066,
                               "actual_capacity_internal_resistance_and_voltage_sag_not_measured": True},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "calculations/esc_v1_budget_inputs.json")
    parser.add_argument("--output", type=Path, default=ROOT / "calculations/esc_v1_budget_results.json")
    args = parser.parse_args()
    p = json.loads(args.input.read_text(encoding="utf-8"))
    result = calculate(p)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mass_totals_g": result["mass_totals_g"],
        "pcb_estimate_g": result["pcb_estimate_g"],
        "wire_mass_total_g": result["wire_mass_total_g"],
        "reference_efficiency": result["reference_point_ideal_induced_to_electrical_power_ratio"],
        "key_scenarios": [x for x in result["performance_scenarios"] if x["mass_g"] in (260, 300, 320) and x["total_thrust_to_weight"] in (1, 2)],
        "bridge_loss_scenarios": result["bridge_loss_scenarios"],
        "gate_driver": result["gate_driver"],
        "wire_electrical_checks": result["wire_electrical_checks"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
