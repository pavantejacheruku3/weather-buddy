"""
Weather Buddy - a real-time weather MCP server.

It uses the free Open-Meteo API (no API key needed).
- Run locally for Claude Desktop:   python server.py
- Run on a cloud server (Render):   TRANSPORT=http python server.py
"""
import os

import httpx
from mcp.server.mcpserver import MCPServer

# Cloud hosts (like Render) tell us which port to use via the PORT variable.
PORT = int(os.environ.get("PORT", 8000))

mcp = MCPServer("Weather Buddy")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def find_city(city: str):
    """Turn a city name into latitude/longitude."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(GEOCODE_URL, params={"name": city, "count": 1})
        r.raise_for_status()
        results = r.json().get("results")
        return results[0] if results else None


@mcp.tool()
async def get_current_weather(city: str) -> str:
    """Get the live, current weather (temperature, wind, rain) for a city."""
    place = await find_city(city)
    if not place:
        return f"Sorry, I couldn't find a city called '{city}'."

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(FORECAST_URL, params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,wind_speed_10m,precipitation",
        })
        r.raise_for_status()
        now = r.json()["current"]

    return (
        f"Weather in {place['name']}, {place.get('country', '')} right now: "
        f"{now['temperature_2m']}°C, wind {now['wind_speed_10m']} km/h, "
        f"rain {now['precipitation']} mm."
    )


@mcp.tool()
async def get_forecast(city: str, days: int = 3) -> str:
    """Get the daily weather forecast for a city (1 to 7 days)."""
    days = max(1, min(days, 7))
    place = await find_city(city)
    if not place:
        return f"Sorry, I couldn't find a city called '{city}'."

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(FORECAST_URL, params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": days,
            "timezone": "auto",
        })
        r.raise_for_status()
        d = r.json()["daily"]

    lines = [f"{days}-day forecast for {place['name']}:"]
    for i, date in enumerate(d["time"]):
        lines.append(
            f"- {date}: {d['temperature_2m_min'][i]}°C to "
            f"{d['temperature_2m_max'][i]}°C, "
            f"rain chance {d['precipitation_probability_max'][i]}%"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    # "stdio" = local mode (Claude Desktop starts this file itself).
    # "http"  = cloud mode (server listens at https://your-url/mcp).
    if os.environ.get("TRANSPORT") == "http":
        # host="0.0.0.0" means "accept connections from outside" (needed in the cloud).
        # stateless_http=True keeps each request independent, which suits cloud hosting.
        mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT,
                stateless_http=True)
    else:
        mcp.run()
