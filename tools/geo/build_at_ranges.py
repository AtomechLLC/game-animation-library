"""Build lib/geo-at.json: the IP ranges RIPE NCC has delegated to holders in Austria.

The site hides its Previewer tab from visitors in Austria (shared/appbar.js asks /geo.json, which lib/geo.js answers
from this file). Hosting has no CDN country header, so the server checks the visitor's IP against RIPE's public
delegation list instead. That list says where the address holder is registered, which is close to where the visitor
is but not exact (VPNs, mobile roaming, multinational networks). Re-run now and then to pick up new delegations:

    python3 tools/geo/build_at_ranges.py            # downloads the latest list
    python3 tools/geo/build_at_ranges.py FILE       # or reads a saved copy of delegated-ripencc-latest
"""
import ipaddress, json, sys, urllib.request

SRC = 'https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest'
CC = 'AT'


def main():
    text = open(sys.argv[1]).read() if len(sys.argv) > 1 else urllib.request.urlopen(SRC).read().decode()
    v4, v6, date = [], [], ''
    for line in text.splitlines():
        f = line.split('|')
        if len(f) >= 7 and f[0] == '2' and not date:
            date = f[5]
        if len(f) < 7 or f[1] != CC or f[6] not in ('allocated', 'assigned'):
            continue
        if f[2] == 'ipv4':
            a = int(ipaddress.IPv4Address(f[3]))
            v4.append([a, a + int(f[4]) - 1])
        elif f[2] == 'ipv6':
            v6.append(f'{f[3]}/{f[4]}')
    # merge touching IPv4 ranges so the server can binary-search them
    v4.sort()
    merged = []
    for a, b in v4:
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    v6 = [str(n) for n in ipaddress.collapse_addresses(ipaddress.IPv6Network(x) for x in v6)]
    out = {'country': CC, 'source': SRC, 'date': date, 'ipv4': merged, 'ipv6': v6}
    with open('lib/geo-at.json', 'w') as fh:
        json.dump(out, fh, separators=(',', ':'))
    print(f'{CC}: {len(merged)} IPv4 ranges, {len(v6)} IPv6 prefixes ({date})')


if __name__ == '__main__':
    main()
