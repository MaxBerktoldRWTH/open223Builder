import random
import string

from rdflib import Namespace, URIRef, Graph
from rdflib.namespace import DefinedNamespace
from rdflib import RDF, RDFS, XSD

S223 = Namespace("http://data.ashrae.org/standard223#")
VISU = Namespace("http://example.org/visualization#")
BLDG = Namespace("http://example.org/building#")
QUDT = Namespace("http://qudt.org/schema/qudt/")
QUDTQK = Namespace("http://qudt.org/vocab/quantitykind/")
QUDTU = Namespace("http://qudt.org/vocab/unit/")


__all__ = [
    "S223",
    "VISU",
    "BLDG",
    "RDF",
    "RDFS",
    "XSD",
    "QUDT",
    "QUDTQK",
    "QUDTU",
    "bindings"
]
bindings = {
    RDF: "rdf",
    RDFS: "rdfs",
    XSD: "xsd",
    S223: "s223",
    BLDG: "bldg",
    VISU: "visu",
    QUDT: "qudt",
    QUDTQK: "qudtqk",
    QUDTU: "qudtu",
}


def replace_last_backslash(s):
    index = s.rfind("/")
    if index != -1:
        return s[:index] + '#' + s[index + 1:]
    return s  # return original if no backslash found


def split_uri(uri):
    uri = str(uri)  # in case it's a URIRef
    for sep in ['#', '/', ':']:
        index = uri.rfind(sep)
        if index != -1:
            namespace = uri[:index + 1]  # include separator
            term = uri[index + 1:]
            return namespace, term
    return "", uri


def find_abbreviation(uri):

    """Find the namespace of a given URI."""

    uri = str(uri)  # in case it's a URIRef

    for ns, short in bindings.items():
        if uri.startswith(str(ns)):
            return short

    return None


def to_label(uri):
    """Converts a URI to a human-readable label."""

    if uri is None:
        return None

    ns, term = split_uri(uri)

    abbreviation = find_abbreviation(uri)

    if abbreviation is None:
        abbreviation = ns

    try:
        return abbreviation + '.' + term

    except TypeError:
        raise TypeError(f"Invalid URI format: {uri}.")


def short_uuid(length: int = 8):

    return ''.join(random.choices(string.ascii_letters, k=length))


def bind_namespaces(g):

    """Add a namespace prefix to a graph."""

    for namespace, prefix in bindings.items():
        g.bind(prefix, namespace)


def replace_namespace(g, oldns, newns):

    new_graph = Graph()

    for s, p, o in g:
        new_s = URIRef(str(s).replace(str(oldns), str(newns))) if isinstance(s, URIRef) and str(s).startswith(
            str(oldns)) else s
        new_p = URIRef(str(p).replace(str(oldns), str(newns))) if isinstance(p, URIRef) and str(p).startswith(
            str(oldns)) else p
        new_o = URIRef(str(o).replace(str(oldns), str(newns))) if isinstance(o, URIRef) and str(o).startswith(
            str(oldns)) else o

        new_graph.add((new_s, new_p, new_o))

    return new_graph


class VISU(DefinedNamespace):

    """ This namespace contains the visualization ontology. """

    _NS = Namespace("http://example.org/visualization#")

    positionX: URIRef  # The x-axis of a connectable.
    positionY: URIRef  # The y-axis of a connectable.
    rotation: URIRef  # The rotation of a connectable.

    relativeX: URIRef  # The relative x-axis of a connection point.
    relativeY: URIRef  # The relative y-axis of a connection point.

    offsetX: URIRef  # The offset x-axis of a property.
    offsetY: URIRef  # The offset y-axis of a property.
    identifier: URIRef  # The identifier of a property.

    width: URIRef  # The width of a domain space or physical space.
    height: URIRef  # The height of a domain space or physical space.


if __name__ == "__main__":

    label = to_label(QUDT.degreeCelsius)

    print(label)

