import time
import docker
import os
import subprocess

client = docker.from_env()

MEASUREMENT_INTERVAL = 0.1
MEASUREMENT_LENGTH = 20

FABRIC_DIR = "/mnt/c/Users/jared/go/src/github.com/fabric"
BLOCKBENCH_DIR = "/mnt/c/Users/jared/go/src/github.com/blockbench/"

BENCHMARK_DIR = BLOCKBENCH_DIR + "benchmark/fabric-v2.2"

CHANNEL_NAME = "mychannel"
CC_NAME = "kvstore"
CC_SRC_PATH = BLOCKBENCH_DIR + f"benchmark/contracts/fabric-v2.2/{CC_NAME}"
MODE = "open_loop"

def setup():
    tear_down()
    # Fix weird issue with WSL2
    subprocess.run("alias docker-credential-desktop=docker-credential-desktop.exe", shell=True)

    # Build docker images
    os.chdir(FABRIC_DIR)
    subprocess.run("make peer-docker -B", shell=True)
    subprocess.run("make orderer-docker -B", shell=True)

    # Network up
    os.chdir(BENCHMARK_DIR)
    subprocess.run(f"./network.sh up createChannel -ca -i 2.2 -c {CHANNEL_NAME}", shell=True)
    os.chdir(BENCHMARK_DIR)
    subprocess.run(f"./network.sh deployCC -ccn {CC_NAME} -ccp {CC_SRC_PATH}", shell=True)

    # Start helper Node servers
    os.chdir("services")
    subprocess.run("rm -rf wallet", shell=True)
    subprocess.run("npm install", shell=True)
    subprocess.run("node enrollAdmin.js", shell=True)
    subprocess.run("node registerUser.js", shell=True)

    subprocess.run(f"node block-server.js {CHANNEL_NAME} 8800 > block-server.log 2>&1 &", shell=True)
    subprocess.run(f"node txn-server.js {CHANNEL_NAME} {CC_NAME} {MODE} 8801 > txn-server-8801.log 2>&1 &", shell=True)
    subprocess.run(f"node txn-server.js {CHANNEL_NAME} {CC_NAME} {MODE} 8802 > txn-server-8802.log 2>&1 &", shell=True)

def tear_down():
    os.chdir(BENCHMARK_DIR)
    subprocess.run("./network.sh down", shell=True)
    subprocess.run("ps aux  |  grep -i block-server  |  awk '{print $2}' | xargs kill -9", shell=True)
    subprocess.run("ps aux  |  grep -i txn-server  |  awk '{print $2}' | xargs kill -9", shell=True)
    os.chdir("services")
    subprocess.run("rm -rf wallet", shell=True)

    # Remove docker stuff
    for container in ["ca_orderer", "ca_org1", "ca_org2", "orderer.example.com", "peer0.org1.example.com", "peer0.org2.example.com"]:
        subprocess.run(f"docker stop {container}", shell=True)
        subprocess.run(f"docker rm -v {container}", shell=True)

    # Remove extra volumes
    for volume in ["net_peer0.org1.example.com", "net_peer0.org2.example.com", "net_orderer.example.com"]:
        subprocess.run(f"docker volume rm {volume}", shell=True)

    subprocess.run("docker network rm net_test", shell=True)

def calculate_cpu_percent(d):
    cpu_count = len(d["cpu_stats"]["cpu_usage"]["percpu_usage"])
    cpu_percent = 0.0
    cpu_delta = float(d["cpu_stats"]["cpu_usage"]["total_usage"]) - \
                float(d["precpu_stats"]["cpu_usage"]["total_usage"])
    system_delta = float(d["cpu_stats"]["system_cpu_usage"]) - \
                   float(d["precpu_stats"]["system_cpu_usage"])
    if system_delta > 0.0:
        cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
    return cpu_percent

def calculate_memory_usage(d):
    return d["memory_stats"]["usage"]

def bytes_to_readable(bytes):
    if bytes > 1024 ** 3:
        return str(int(bytes / (1024 ** 3))) + " GB"
    if bytes > 1024 ** 2:
        return str(int(bytes / (1024 ** 2))) + " MB"
    if bytes > 1024:
        return str(int(bytes / (1024 ** 3))) + " KB"
    return str(bytes) + " B"

def snapshot(container):
    stats = container.stats(stream=False)
    return {
        "memory": calculate_memory_usage(stats),
        "cpu": calculate_cpu_percent(stats)
    }

def run_sim():
    setup()
    for i in range(0, int(MEASUREMENT_LENGTH / MEASUREMENT_INTERVAL)):
        print(snapshot(client.containers.list()[1]))
        time.sleep(MEASUREMENT_INTERVAL)
    tear_down()

# run_sim()
tear_down()