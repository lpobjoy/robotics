from setuptools import find_packages, setup

package_name = "vda5050_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/launch",
            ["launch/bridge.launch.py", "launch/headless_sim.launch.py"],
        ),
    ],
    install_requires=["setuptools", "paho-mqtt"],
    zip_safe=True,
    maintainer="Lewis Pobjoy",
    maintainer_email="lpobjoy@gmail.com",
    description=(
        "Subscribes to VDA 5050 order/instantActions over MQTT and drives Nav2; "
        "publishes VDA 5050 state/visualization/connection back."
    ),
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "bridge_node = vda5050_bridge.bridge_node:main",
        ],
    },
)
