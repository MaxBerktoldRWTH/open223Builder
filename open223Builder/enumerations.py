from typing import List
from rdflib import URIRef
from open223Builder.ontology.namespaces import S223, QUDT, QUDTQK, QUDTU


__all__ = [
    "domains",
    "roles",
    "aspects",
    "units",
    "quantity_kinds",
]


domains: List[URIRef] = [
    S223['Domain-Lighting'],
    S223['Domain-Electrical'],
    S223['Domain-HVAC'],
    S223['Domain-Occupancy'],
    S223['Domain-Plumbing'],
    S223['Domain-Refrigeration'],
    S223['Domain-Electrical'],
    S223['Domain-FireProtection'],
    S223['Domain-Plumbing'],
]

roles: List[URIRef] = [
    S223['Role-Condenser'],
    S223['Role-Cooling'],
    S223['Role-Dehumidifying'],
    S223['Role-Discharge'],
    S223['Role-Economizer'],
    S223['Role-Evaporator'],
    S223['Role-Exhaust'],
    S223['Role-Expansion'],
    S223['Role-Generator'],
    S223['Role-Heating'],
    S223['Role-HeatRecovery'],
    S223['Role-HeatTransfer'],
    S223['Role-Load'],
    S223['Role-OutdoorAirIntake'],
    S223['Role-Primary'],
    S223['Role-Recirculating'],
    S223['Role-Relief'],
    S223['Role-Return'],
    S223['Role-Secondary'],
    S223['Role-Supply'],
]

aspects: List[URIRef] = [
    S223['s223.Aspect-Alarm'],
    S223['s223.Aspect-CatalogNumber'],
    S223['s223.Aspect-Deadband'],
    S223['s223.Aspect-Delta'],
    S223['s223.Aspect-Fault'],
    S223['s223.Aspect-HighLimit'],
    S223['s223.Aspect-LowLimit'],
    S223['s223.Aspect-Manufacturer'],
    S223['s223.Aspect-Maximum'],
    S223['s223.Aspect-Minimum'],
    S223['s223.Aspect-Model'],
    S223['s223.Aspect-Nominal'],
    S223['s223.Aspect-OperatingMode'],
    S223['s223.Aspect-OperatingStatus'],
    S223['s223.Aspect-Rated'],
    S223['s223.Aspect-SerialNumber'],
    S223['s223.Aspect-Setpoint'],
    S223['s223.Aspect-Threshold'],
]

units: List[URIRef] = [
    QUDTU.DEG_C,         # Celsius
    QUDTU.DEG_F,         # Fahrenheit
    QUDTU.K,             # Kelvin
    QUDTU.HZ,            # Hertz
    QUDTU.J,             # Joule
    QUDTU.KiloW,         # Kilowatt
    QUDTU.PA,            # Pascal
    QUDTU.V,             # Volt
    QUDTU.Percent,       # Percent
    QUDTU['KiloW-HR'],   # Kilowatt-hour
    QUDTU.Watt,          # Watt
]

quantity_kinds: List[URIRef] = [

    QUDTQK.Time,
    QUDTQK.Temperature,
    QUDTQK.RelativeHumidity,
    QUDTQK.Illuminance,
    QUDTQK.Frequency,
    QUDTQK.Speed,
    QUDTQK.OpeningRatio,

    QUDTQK.VolumeFlowRate,
    QUDTQK.MassFlowRate,
    QUDTQK.Pressure,

    QUDTQK.Efficiency,
    QUDTQK.ThermalConductivity,

    QUDTQK.Power,
    QUDTQK.Energy,
    QUDTQK.EnergyPerUnitArea,

    QUDTQK.Lenghth,
    QUDTQK.Area,
    QUDTQK.Volume,
]


if __name__ == '__main__':

    print(QUDT.DeG_C)

