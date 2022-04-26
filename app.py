from flask import Flask, request, jsonify, make_response, render_template
import json
import random
import requests
import urllib3
from os import getenv
import datetime


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app = Flask(__name__)

pfsense_username = getenv('PFSENSE_USERNAME')
pfsense_password = getenv('PFSENSE_PASSWORD')
pfsense_host = getenv('PFSENSE_HOST', 'https://192.168.10.1')
params = {"client-id": pfsense_username, "client-token": pfsense_password}

montreal_alias_name = "MULLVAD_CANADA_VPN"
new_york_alias_name = "MULLVAD_USA_VPN"
netherlands_alias_name = "MULLVAD_NETHERLANDS_VPN"

def apply_vpn(IPs, alias):
    address = []
    detail = []
    for k,v in IPs.items():
        if k == '':
            continue
        address.append(k)
        detail.append(v)
    body = {}
    body['id'] = alias
    body['address'] = address
    body['detail'] = detail
    body["client-id"] = pfsense_username
    body["client-token"] = pfsense_password
    body["apply"] = True

    requests.put(f"{pfsense_host}/api/v1/firewall/alias", json.dumps(body), verify = False)

def get_vpn_connections():
    aliases = requests.get(f"{pfsense_host}/api/v1/firewall/alias", params = params, verify=False).json()["data"]

    montreal_alias = [d for d in aliases if d['name'] == montreal_alias_name][0]
    new_york_alias = [d for d in aliases if d['name'] == new_york_alias_name][0]
    netherlands_alias = [d for d in aliases if d['name'] == netherlands_alias_name][0]
    montreal_vpn_addresses = montreal_alias["address"].split(" ")
    montreal_vpn_details = montreal_alias["detail"].split("||")
    new_york_vpn_addresses = new_york_alias["address"].split(" ")
    new_york_vpn_details = new_york_alias["detail"].split("||")
    netherlands_vpn_addresses = netherlands_alias["address"].split(" ")
    netherlands_vpn_details = netherlands_alias["detail"].split("||")

    vpn_status = {}

    vpn_status[montreal_alias_name] = {}
    for i,ip in enumerate(montreal_vpn_addresses):
        vpn_status[montreal_alias_name][ip] = montreal_vpn_details[i]

    vpn_status[new_york_alias_name] = {}
    for i,ip in enumerate(new_york_vpn_addresses):
        vpn_status[new_york_alias_name][ip] = new_york_vpn_details[i]

    vpn_status[netherlands_alias_name] = {}
    for i,ip in enumerate(netherlands_vpn_addresses):
        vpn_status[netherlands_alias_name][ip] = netherlands_vpn_details[i]

    return vpn_status

def add_ip(ip, alias):
    active_connections = get_vpn_connections()[alias]
    active_connections[ip] = f"Added by VPN manager on {datetime.date.today()}"
    apply_vpn(active_connections, alias)



def purge_ip(ip):
    vpn_status = get_vpn_connections()

    for alias, IPs in vpn_status.items():
        if ip in IPs:
            print(f"INFO :: Found active connection for {ip} in {alias}. Deleting...")
            del IPs[ip]
    for alias, IPs in vpn_status.items():
        apply_vpn(IPs, alias)

def get_active_vpn(ip):
    vpn_status = get_vpn_connections()
    current_vpn = "none"
    found = False

    for endpoint, IPs in vpn_status.items():
        if ip in IPs:
            if found:
                print("ERROR :: IP found in multiple lists, fixing status...")
                purge_ip(ip)
                current_vpn = "none"
                break
            current_vpn = endpoint
            found = True
    return current_vpn


@app.route('/active_vpn', methods=["GET"])
def get_vpn():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr
    
    current_vpn = get_active_vpn(ip)
    return jsonify({"vpn": current_vpn})


@app.route('/activate_vpn', methods=["POST"])
def use_vpn():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr

    print(f"INFO :: Making sure {ip} is not currently active...")
    purge_ip(ip)
    input_json = request.get_json(force = True)
    alias = input_json["vpn"]
    if alias != "none":
        add_ip(ip, alias)
        print(f"INFO :: Using {alias} for {ip}")
    else:
        print(f"INFO :: Disabling VPN for {ip}")
    return make_response(jsonify({}), 200)


@app.route('/', methods=["GET"])
def index():
    if "X-Real-IP" in request.headers:
        ip = request.headers["X-Real-IP"]
    else:
        ip = request.remote_addr
    
    return render_template("index.html", ip=ip, active=get_active_vpn(ip))