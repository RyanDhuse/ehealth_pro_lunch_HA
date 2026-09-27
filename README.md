# Health-e Pro Menu — Home Assistant Integration
## **AI DISCLOSURE** This was made by claude.ai
A Home Assistant custom integration that pulls school lunch and breakfast menus from [Health-e Pro](https://www.healthepro.com) and surfaces them as sensors for your Lovelace dashboard.

Works for **any school district** using Health-e Pro's public menu system — just paste the menu URL.

## Installation via HACS

1. In HACS → Integrations → ⋮ (top right) → **Custom repositories**
2. Add: `https://github.com/kane9287/ehealth_pro_lunch_HA` — Category: **Integration**
3. Install **Health-e Pro Menu**
4. Restart Home Assistant

## Manual installation

Copy `custom_components/healthepro_menu/` into your HA `config/custom_components/` directory and restart.

## Configuration

Settings → Integrations → Add Integration → **Health-e Pro Menu**

Paste your school's public menu URL, find it here:
```
https://menus.healthepro.com/
```

The integration auto-discovers the school name, site, and menu details.

## Entities

Three sensors are created per configured menu:

| Entity | State | Key Attributes |
| --- | --- | --- |
| `sensor.*_today` | Today's entrées or "No school" | `off_day`, `off_day_reason`, `entrees`, `sections` |
| `sensor.*_tomorrow` | Tomorrow's entrées or "No school" | same |
| `sensor.*_month` | "N days loaded" | `days` (full list), `published_months` |

## Lovelace example

```yaml
type: markdown
content: |
  {% set s = 'sensor.elementary_schools_elementary_lunch_2025_26_today' %}
  ## Today's Lunch — {{ state_attr(s, 'date') }}
  {% if state_attr(s, 'off_day') %}
  **No school** — {{ state_attr(s, 'off_day_reason') }}
  {% elif states(s) in ['unknown','unavailable','Menu unavailable'] %}
  _Menu unavailable_
  {% else %}
  **Entrées:** {{ state_attr(s, 'entrees') | join(', ') }}
  {% set t = state_attr(s, 'sections') or {} %}
  {% for label in ['Vegetables','Fruit','Milk'] %}
  {% if t.get(label) %}**{{ label }}:** {{ t[label] | join(', ') }}
  {% endif %}{% endfor %}
  {% endif %}
```

## Options

After setup, click **Configure** on the integration:

| Option | Default | Description |
| --- | --- | --- |
| Refresh interval | 24 hours | How often to poll Health-e Pro |
| Prefetch next month | On | Load next month in advance |
| Include recipe details | Off | Fetch allergens & nutrition (extra API calls) |
| Include prices | Off | Fetch meal pricing |
| Include sidebars | Off | Fetch announcements |

## Automation example

```yaml
alias: School lunch reminder
trigger:
  - platform: time
    at: "06:30:00"
condition:
  - condition: template
    value_template: "{{ not state_attr('sensor.elementary_schools_elementary_lunch_2025_26_today', 'off_day') }}"
action:
  - service: notify.mobile_app_phone
    data:
      title: "School Lunch Today"
      message: "{{ states('sensor.elementary_schools_elementary_lunch_2025_26_today') }}"
```

## Supported vendors

Currently supports **Health-e Pro** (`menus.healthepro.com`). Designed with a vendor-neutral internal model so future adapters (LINQ, Nutrislice) can be added without changing the dashboard layer.

## Contributing

Issues and PRs welcome at [github.com/kane9287/ehealth_pro_lunch_HA](https://github.com/kane9287/ehealth_pro_lunch_HA).
