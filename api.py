import re
import yaml
import tempfile
import subprocess

import networkx as nx

from settings import JUJSVG


class JujuSVGException(Exception):
    def __init__(self, cmd, msg):
        self.cmd = cmd
        self.msg = msg


class BundleFormatException(Exception):
    def __init__(self, msg):
        self.msg = msg


def parse_bundle_id(bundle_id):
    m = re.match(r'cs(:~[a-z0-9-_]+/|:)bundle/[a-z0-9-]+-[0-9]+', bundle_id)
    if not m:
        return None

    bundle_path = m.group(0).replace('cs:', '')
    url = 'https://api.jujucharms.com/v4/%s/archive/bundle.yaml' % bundle_path
    diagram_url = 'https://api.jujucharms.com/v4/%s/diagram.svg' % bundle_path
    return (url, diagram_url)


def split_rel(r):
    return r.split(':', 1)


def mapply(func, g, **kwargs):
    args = {}
    for name in func.__code__.co_varnames:
        if name in kwargs:
            args[name] = kwargs[name]
    return func(g, **args)


# https://gist.github.com/bcsaller/adca309ba7abef2e8caf#file-place_bundle-py-L46
def layout(bundle, algo, scale=500.0):
    g = nx.MultiGraph()
    # In Juju 2.0 'services' was replaced by 'applications'.
    services = bundle.get('services') or bundle.get('applications')
    for service in services:
        g.add_node(service)

    for relation in bundle['relations']:
        src = split_rel(relation[0])[0]
        tgts = relation[1]
        if isinstance(tgts, str):
            tgts = [tgts]
        for tgt in tgts:
            tgt = split_rel(tgt)[0]
            g.add_edge(src, tgt)
    pos = mapply(algo, g, k=45, iterations=100)

    for service, data in list(services.items()):
        data['annotations'] = {
            "gui-x": float(pos[service][0]) * scale,
            "gui-y": float(pos[service][1]) * scale,
        }
    return g


def process_bundle(bundle):
    # In Juju 2.0 'services' is replaced by 'applications'
    no_services = 'services' not in bundle and 'applications' not in bundle
    if len(bundle) > 1 and no_services:
        raise BundleFormatException('This bundle has multiple deployments.')

    if no_services:
        bundle = next(iter(bundle.values()))
        no_services = 'services' not in bundle and 'applications' not in bundle
        if no_services:
            raise BundleFormatException('This bundle has no applications.')

    annotations = False
    # In Juju 2.0 'services' was replaced by 'applications'.
    services = bundle.get('services') or bundle.get('applications')
    for service, srvc_data in services.items():
        if 'annotations' in list(srvc_data.keys()):
            annotations = True
            break

    if not annotations:
        # layout = 'circular'
        # algo = getattr(nx, layout + '_layout', None)
        layout(bundle, nx.circular_layout)

    with tempfile.NamedTemporaryFile() as f:
        f.write(yaml.dump(bundle, default_flow_style=False))
        f.flush()
        try:
            svg = subprocess.check_output([JUJSVG, f.name],
                                          stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise JujuSVGException(' '.join(e.cmd), e.output)
    return svg
