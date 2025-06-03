# Electricity Price Levels for Home Assistant

A custom component for Home Assistant that provides electricity price level sensors based on data from the Home Assistant NordPool integration. This integration helps you monitor and automate your home based on real-time and forecasted electricity prices, using the NordPool sensor as a data source.

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/klurige)

## Features
- Uses electricity prices provided by the Home Assistant NordPool integration.
- Categorizes prices into levels (e.g., low, medium, high).
- Provides sensors for use in automations and dashboards.
- Supports multiple languages (English, Swedish).

## Prerequisites
- You must have the [NordPool integration](https://github.com/custom-components/nordpool) installed and configured in Home Assistant. This integration supplies the electricity price sensor that this component depends on.

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
- Fill in the name of your NordPool sensor and press `Submit`

### Option 2: Manual
1. Copy the `custom_components/electricitypricelevels` directory into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. Add the integration via the Home Assistant UI or YAML configuration.

## Configuration
You can configure the integration via the Home Assistant UI (recommended) or manually in `configuration.yaml`:

```yaml
# Example configuration.yaml entry
# (if manual configuration is supported)
electricitypricelevels:
  region: "SE3"
  price_entity: "sensor.nordpool_kwh_se3_sek_3_10_0"
```

There are many extra fees and taxes that can be added to the price. These can be added in the
configuration of the integration. The configuration can be found in the integration settings.

I have added to the configuration taxes and fees added by my grid and supplier. They are no doubt
called differently for other grids and suppliers.

| Key                      | Description              |
|--------------------------|--------------------------|
| `nordpool_area_id`     | Nord Pool Area id        |
| `supplier_balancing_fee`   | Supplier balancing fee   |
| `supplier_environment_fee` | Supplier environment fee |
| `supplier_certificate_fee` | Supplier certificate fee |
| `supplier_fixed_fee`     | Supplier fixed fee       |
| `supplier_credit`        | Supplier credit          |
| `grid_fixed_fee`         | Grid fixed fee           |
| `grid_variable_fee`      | Grid variable fee        |
| `grid_energy_tax`        | Grid energy tax          |
| `electricity_vat`        | Electricity VAT          |
| `grid_fixed_credit`      | Grid fixed credit        |
| `grid_variable_credit`   | Grid variable credit     |

## Usage
- The integration will create two sensors, `sensor.electricity_price` and `sensor.iso_formatted_time`.
  - `sensor.electricity_price` provides the current electricity price with all fees and taxes included, and a list of all known upcoming prices. (Nordpool gets the next day prices around 14:00 CET)
  - `sensor.iso_formatted_time` provides the current time in ISO 8601 format, and a string containing one character for each price level. ( Level clock pattern. See https://github.com/Klurige/LevelIndicatorClock)
- Use these sensors in automations to optimize energy usage (e.g., run appliances when prices are low).

### `sensor.electricity_price`
- **Description:** The current electricity price, including all configured fees and taxes.
- **State:** The numeric value of the current price.
- **Attributes:**
  - `spot_price`: The base price from the NordPool sensor (before fees/taxes).
  - `cost`: The total cost including all fees and taxes.
  - `credit`: The total credit received when exporting electricity.
  - `unit`: The unit for the electricity power. Typically `kWh`.
  - `currency`: The currency of the price, for example `SEK` or `EUR`.
  - `level`: Current price level as a string (`Low`, `Medium`, `High`).
  - `rank`: The current rank of the price compared to other prices for the current day. See the [Ranking](#ranking) section for details.
  - `low_threshold`: The threshold for low prices.
  - `high_threshold`: The threshold for high prices.
  - `rates`: A list of today's (and possibly tomorrow's) prices, each with:
    - `start`: The start time of the price period.
    - `end`: The end time of the price period. 1us before the next period starts.
    - `spot_price`: The base price from the NordPool sensor for that period.
    - `cost`: The total cost for that period, including all fees and taxes.
    - `credit`: The total credit for that period, if applicable.
    - `level`: The price level for that period.
    - `rank`: The rank of the price for that period compared to other prices for the current day.
- **Update Frequency:** Updated every time a new price slot is entered. (See the NordPool integration for details on update frequency.)

### `sensor.iso_formatted_time`
- **Description:** The current time in ISO 8601 format. Useful for advanced automations and templating. Main purpose is to provide data for the Level Indicator Clock (https://github.com/Klurige/LevelIndicatorClock)
- **State:** The current time as a string (e.g., `2025-06-03T14:00:00+02:00`).
- **Attributes:**
  - `level_clock_pattern`: A string representing the current price level pattern, where each character corresponds to a price level for today and tomorrow. Each character represents 12 minutes, with:
    - `L` for Low
    - `M` for Medium
    - `H` for High
    - `U` for Unknown (if no price is available for that period)
    - `S` for selling (exporting). To be implemented.
    - `E` for internal error.
- **Update Frequency:** Updated every minute.

## Ranking
The `sensor.electricity_price` sensor provides a `rank` attribute that indicates the current price's rank compared to other prices for the current day. The rank is calculated on the price level of the current price.
- `1` is the lowest price for the day.
- `100` is the highest price for the day.

For example, to find the three cheapest hours of the day, the rank should be lower than 13. 3/24 hours in a day, so 3 cheapest hours is 3/24 * 100 = 12.5, rounded up to 13.
Note that this will find non-consecutive time slots.

#### Notes
- The sensors rely on the NordPool integration for price updates. If the NordPool sensor is delayed or unavailable, these sensors will reflect the latest available data.
- The `rates` attribute in the price sensor provides a forecast of upcoming prices and levels, which can be used for advanced automations or visualizations.

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
      name: Electricity Price
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

## Contributing
Contributions are welcome! Please open issues or pull requests on GitHub.

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

## License
GPL https://www.gnu.org/licenses/gpl-3.0.txt
