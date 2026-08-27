"""Read and edit FEBio (.feb) input files.

.feb files are XML. The relevant sections this module works with:

    Mesh/Nodes/node[@id]                        -- "x,y,z" text
    Mesh/Elements[@type][@name]/elem[@id]        -- comma-separated node ids
    Mesh/Surface[@name]/*[@id]                   -- comma-separated node ids (facets)
    MeshDomains/SolidDomain[@name][@mat]         -- links a part to a material
    Material/material[@name]/<property>          -- e.g. <E>1.0</E>
    Loads/surface_load[@surface]/pressure        -- pressure magnitude
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

# FEBio does not accept UTF-8 declarations; files must round-trip as ISO-8859-1.
FEBIO_ENCODING = "ISO-8859-1"


class FebModel:
    """A parsed .feb file, with helpers for the edits FEA runs commonly need."""

    def __init__(self, tree: ET.ElementTree):
        self.tree = tree
        self.root = tree.getroot()

    @classmethod
    def from_file(cls, path: str | Path) -> "FebModel":
        return cls(ET.parse(path))

    def save(self, path: str | Path) -> None:
        self.tree.write(path, xml_declaration=True, encoding=FEBIO_ENCODING)

    # -- nodes ---------------------------------------------------------

    def _node_element(self, node_id: int) -> ET.Element:
        node = self.root.find(f".//Nodes/node[@id='{node_id}']")
        if node is None:
            raise KeyError(f"No node with id {node_id}")
        return node

    def get_node_coordinates(self, node_id: int) -> tuple[float, float, float]:
        x, y, z = self._node_element(node_id).text.split(",")
        return float(x), float(y), float(z)

    def set_node_coordinates(self, node_id: int, xyz: tuple[float, float, float]) -> None:
        self._node_element(node_id).text = ",".join(str(v) for v in xyz)

    def set_node_coordinates_bulk(self, coordinates: dict[int, tuple[float, float, float]]) -> None:
        for node_id, xyz in coordinates.items():
            self.set_node_coordinates(node_id, xyz)

    def get_all_node_coordinates(self) -> dict[int, tuple[float, float, float]]:
        """Every node in the mesh, across all (possibly multiple, named) Nodes blocks."""
        result = {}
        for node in self.root.findall(".//Nodes/node"):
            x, y, z = node.text.split(",")
            result[int(node.get("id"))] = (float(x), float(y), float(z))
        return result

    def get_named_node_ids(self, nodes_block_name: str) -> set[int]:
        """Ids in a named Nodes block (FEBioStudio tags nodes by source object this way)."""
        block = self.root.find(f".//Nodes[@name='{nodes_block_name}']")
        if block is None:
            raise KeyError(f"No Nodes block named {nodes_block_name!r}")
        return {int(n.get("id")) for n in block.findall("node")}

    # -- named node sets -------------------------------------------------

    def get_nodeset_ids(self, nodeset_name: str) -> list[int]:
        nodes = self.root.find(f".//Mesh/NodeSet[@name='{nodeset_name}']")
        if nodes is None:
            raise KeyError(f"No NodeSet named {nodeset_name!r}")
        return [int(n.get("id")) for n in nodes.findall("node")]

    # -- parts / elements --------------------------------------------------

    def get_part_node_ids(self, part_name: str) -> set[int]:
        """All node ids referenced by the elements of a part (any element type)."""
        elements = self.root.find(f".//Mesh/Elements[@name='{part_name}']")
        if elements is None:
            raise KeyError(f"No part named {part_name!r}")
        return self._ids_from_facet_text(elements)

    def get_surface_node_ids(self, surface_name: str) -> set[int]:
        """All node ids referenced by the facets of a named surface."""
        surface = self.root.find(f".//Mesh/Surface[@name='{surface_name}']")
        if surface is None:
            raise KeyError(f"No surface named {surface_name!r}")
        return self._ids_from_facet_text(surface)

    @staticmethod
    def _ids_from_facet_text(container: ET.Element) -> set[int]:
        ids: set[int] = set()
        for facet in container:
            if facet.text:
                ids.update(int(n) for n in facet.text.strip().split(","))
        return ids

    # -- materials -----------------------------------------------------

    def get_parts_by_material(self, material_name: str) -> list[str]:
        mesh_domains = self.root.find("MeshDomains")
        if mesh_domains is None:
            return []
        return [
            domain.get("name")
            for domain in mesh_domains
            if domain.get("mat") == material_name
        ]

    def _material_element(self, material_name: str) -> ET.Element:
        material = self.root.find(f".//Material/material[@name='{material_name}']")
        if material is None:
            raise KeyError(f"No material named {material_name!r}")
        return material

    def get_material_property(self, material_name: str, property_name: str) -> str:
        material = self._material_element(material_name)
        prop = material.find(property_name)
        if prop is None:
            raise KeyError(f"Material {material_name!r} has no property {property_name!r}")
        return prop.text

    def set_material_property(self, material_name: str, property_name: str, value) -> None:
        material = self._material_element(material_name)
        prop = material.find(property_name)
        if prop is None:
            raise KeyError(f"Material {material_name!r} has no property {property_name!r}")
        prop.text = str(value)

    # -- loads -----------------------------------------------------------

    def get_pressure_loads(self) -> dict[str, float]:
        """Maps each pressure surface_load's `surface` attribute to its current value."""
        loads = self.root.find("Loads")
        if loads is None:
            return {}
        result = {}
        for surface_load in loads.findall("surface_load"):
            pressure = surface_load.find("pressure")
            if pressure is not None:
                result[surface_load.get("surface")] = float(pressure.text)
        return result

    def set_pressure_load(self, value, surface_name: str | None = None) -> None:
        """Set a pressure load's value.

        If `surface_name` is given, only the surface_load for that surface is
        updated. If omitted, there must be exactly one pressure surface_load
        in the file -- with more than one present, `surface_name` is required
        so a value doesn't get applied to the wrong surface.
        """
        loads = self.root.find("Loads")
        if loads is None:
            raise KeyError("File has no Loads section")

        candidates = [
            surface_load
            for surface_load in loads.findall("surface_load")
            if surface_load.find("pressure") is not None
            and (surface_name is None or surface_load.get("surface") == surface_name)
        ]

        if not candidates:
            target = f"surface {surface_name!r}" if surface_name else "any surface"
            raise KeyError(f"No pressure surface_load found for {target}")
        if surface_name is None and len(candidates) > 1:
            surfaces = [c.get("surface") for c in candidates]
            raise ValueError(
                f"Multiple pressure loads present ({surfaces}); pass surface_name to disambiguate"
            )

        for surface_load in candidates:
            surface_load.find("pressure").text = str(value)
