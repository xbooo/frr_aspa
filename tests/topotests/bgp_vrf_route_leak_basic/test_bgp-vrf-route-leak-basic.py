#!/usr/bin/env python

#
# test_bgp-vrf-route-leak-basic.py
#
# Copyright (c) 2018 Cumulus Networks, Inc.
#                    Donald Sharp
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND Cumulus Networks DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NETDEF BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

"""
test_bgp-vrf-route-leak-basic.py.py: Test basic vrf route leaking
"""

import json
import os
import sys
from functools import partial
import pytest

CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, "../"))

# pylint: disable=C0413
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

from mininet.topo import Topo


class BGPVRFTopo(Topo):
    def build(self, *_args, **_opts):
        "Build function"
        tgen = get_topogen(self)

        for routern in range(1, 2):
            tgen.add_router("r{}".format(routern))


def setup_module(mod):
    "Sets up the pytest environment"
    tgen = Topogen(BGPVRFTopo, mod.__name__)
    tgen.start_topology()

    # For all registered routers, load the zebra configuration file
    for rname, router in tgen.routers().items():
        router.run("/bin/bash {}/setup_vrfs".format(CWD))
        router.load_config(
            TopoRouter.RD_ZEBRA, os.path.join(CWD, "{}/zebra.conf".format(rname))
        )
        router.load_config(
            TopoRouter.RD_BGP, os.path.join(CWD, "{}/bgpd.conf".format(rname))
        )

    # After loading the configurations, this function loads configured daemons.
    tgen.start_router()
    # tgen.mininet_cli()


def teardown_module(mod):
    "Teardown the pytest environment"
    tgen = get_topogen()

    # This function tears down the whole topology.
    tgen.stop_topology()


def test_vrf_route_leak():
    logger.info("Ensure that routes are leaked back and forth")
    tgen = get_topogen()
    # Don't run this test if we have any failure.
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    r1 = tgen.gears["r1"]

    # Test DONNA VRF.
    expect = {
        "10.0.0.0/24": [
            {
                "protocol": "connected",
            }
        ],
        "10.0.1.0/24": [
            {"protocol": "bgp", "selected": True, "nexthops": [{"fib": True}]}
        ],
        "10.0.2.0/24": [{"protocol": "connected"}],
        "10.0.3.0/24": [
            {"protocol": "bgp", "selected": True, "nexthops": [{"fib": True}]}
        ],
    }

    test_func = partial(
        topotest.router_json_cmp, r1, "show ip route vrf DONNA json", expect
    )
    result, diff = topotest.run_and_expect(test_func, None, count=10, wait=0.5)
    assert result, "BGP VRF DONNA check failed:\n{}".format(diff)

    # Test EVA VRF.
    expect = {
        "10.0.0.0/24": [
            {"protocol": "bgp", "selected": True, "nexthops": [{"fib": True}]}
        ],
        "10.0.1.0/24": [
            {
                "protocol": "connected",
            }
        ],
        "10.0.2.0/24": [
            {"protocol": "bgp", "selected": True, "nexthops": [{"fib": True}]}
        ],
        "10.0.3.0/24": [
            {
                "protocol": "connected",
            }
        ],
    }

    test_func = partial(
        topotest.router_json_cmp, r1, "show ip route vrf EVA json", expect
    )
    result, diff = topotest.run_and_expect(test_func, None, count=10, wait=0.5)
    assert result, "BGP VRF EVA check failed:\n{}".format(diff)


def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip("Memory leak test/report is disabled")

    tgen.report_memory_leaks()


if __name__ == "__main__":
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
