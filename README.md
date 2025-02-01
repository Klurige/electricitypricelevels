# Electricity Price Levels for Home Assistant
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/klurige)

This integration provides electricity price levels, stemming from the Nord Pool electricity market.

The electricity price you actually pay is the sum of the electricity price and various fees and taxes. 
The electricity price is the price of the electricity itself, while the fees and taxes are added on top.

This integration allows for adding all these fees and taxes to the price and provides the total price
you pay for electricity.
It also allows for setting a high and low price level, which can be used for automation in Home Assistant.

Nord Pool is a service provider that operates an electricity market and power system services, including the exchange of electricity on a spot market Nordics and Baltic countries.

This integration assumes that you have the Nordpool integration sensor in Home Assistant.
Note that the built-in Nordpool integration can currently not be used, as it does not provide the
necessary data for this integration. The Nordpool integration sensor can be found [here](


[ApexCharts](https://github.com/RomRider/apexcharts-card) card is recommended for visualization of the data in Home Assistant.<br>
<img src="https://user-images.githubusercontent.com/5879533/210006998-d8ebd401-5a92-471d-9072-4e6b1c69b779.png" width="500"/>

### Table of Contents
**[Installation](#installation)**<br>
**[Usage](#usage)**<br>
**[Other](#other)**<br>
**[Troubleshooting](#troubleshooting)**<br>

## Installation

### Option 1: HACS

- Follow [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=custom-components&repository=electricitypricelevels&category=integration) and install it
- Restart Home Assistant

  *or*
- Go to `HACS` -> `Integrations`,
- Select `+`,
- Search for `electricitypricelevels` and install it,
- Restart Home Assistant

#### Add the integration via the Home Assistant UI
- Go to `Settings` -> `Devices & Services`
- Select `+ Add Integration`
- Search for `electricitypricelevels` and select it
- Fill in the name of your nordpool sensor and press `Submit`


### Option 2: Manual
Coming soon

## Configuration
There are many extra fees and taxes that can be added to the price. These can be added in the
configuration of the integration. The configuration can be found in the integration settings.

I have added to the configuration taxes and fees added by my grid and supplier. They are no doubt
called differently for other grids and suppliers.

| Key                      | Description                 |
|--------------------------|-----------------------------|
| `nordpool_sensor_id`     | Name of the Nordpool sensor |
| `supplier_balancing_fee`   | Supplier balancing fee      |
| `supplier_environment_fee` | Supplier environment fee    |
| `supplier_certificate_fee` | Supplier certificate fee    |
| `supplier_fixed_fee`     | Supplier fixed fee          |
| `supplier_credit`        | Supplier credit             |
| `grid_fixed_fee`         | Grid fixed fee              |
| `grid_variable_fee`      | Grid variable fee           |
| `grid_energy_tax`        | Grid energy tax             |
| `electricity_vat`        | Electricity VAT             |
| `grid_fixed_credit`      | Grid fixed credit           |
| `grid_variable_credit`   | Grid variable credit        |


## Sensors

| Entity ID                   | Description            |
|-----------------------------|------------------------|
| `sensor.iso_formatted_time` | Time in ISO format.    |
| `sensor.electricity_price`  | Price for electricity. |

## Visualisation
The data can be visualized using the ApexCharts card.
Here is an example of how the data can be visualized in Home Assistant.
Also needed is the ´config-template-card´.

```yaml
type: custom:config-template-card
variables:
  thresholdLow: states["sensor.electricity_price"].attributes.low_threshold
  thresholdHigh: states["sensor.electricity_price"].attributes.high_threshold
entities:
  - sensor.electricity_price
card:
  type: custom:apexcharts-card
  graph_span: 48h
  span:
    start: day
  experimental:
    color_threshold: true
  series:
    - entity: sensor.electricity_price
      name: Köp
      type: column
      color: green
      float_precision: 2
      extend_to: end
      data_generator: |
        return entity.attributes.rates.map((rate, index) => {
          return [new Date(rate["start"]).getTime(), rate["cost"]];
        });
      color_threshold:
        - value: -1000000
          color: green
        - value: ${vars.thresholdLow}
          color: yellow
        - value: ${vars.thresholdHigh}
          color: red
```
## Troubleshooting
  "mounts": [
  "source=/home/cid13773/projects/ha/ha_dev/levelindicatorclock/dist,target=/workspaces/home-assistant-core/config/www/levelindicatorclock,type=bind,consistency=cached",
  "source=/home/cid13773/projects/ha/ha_dev/electricitypricelevels/custom_components/electricitypricelevels,target=/workspaces/home-assistant-core/config/custom_components/electricitypricelevels,type=bind,consistency=cached"
],

### Debug logging
Add this to your `configuration.yaml` and restart Home Assistant to debug the component.

```yaml
logger:
  default: info
  logs:
    custom_components.electricitypricelevels.sensor.electricity_price_level_sensor: info
    custom_components.electricitypricelevels.sensor.time_sensor: info
    custom_components.electricitypricelevels.util: debug

```
