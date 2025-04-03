import sys # For printing to stderr
import traceback # For detailed error logging
from typing import Any, Dict, Optional # Use Dict for clarity
import httpx
import json # For JSONDecodeError
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
# Be specific with User-Agent as requested by NWS: (YourApp/Version ContactEmailOrURL)
USER_AGENT = "MCPWeatherApp/1.0 (github.com/your-repo-or-contact)"

# --- Logging Helper ---
def log_error(message: str):
    """Logs an error message to stderr."""
    print(f"SERVER ERROR: {message}", file=sys.stderr)

async def make_nws_request(url: str) -> Optional[Dict[str, Any]]:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    # Add basic logging for the request
    print(f"SERVER INFO: Making NWS request to {url}", file=sys.stderr)
    async with httpx.AsyncClient(follow_redirects=True) as client: # Follow redirects
        try:
            response = await client.get(url, headers=headers, timeout=20.0) # Slightly shorter timeout
            response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx
            # Check content type before decoding JSON
            content_type = response.headers.get("content-type", "")
            if "application/geo+json" not in content_type and "application/ld+json" not in content_type:
                 log_error(f"Unexpected content type received from {url}: {content_type}")
                 # Optionally return the raw text if needed, or None/error
                 # return {"error": "Unexpected content type", "content": response.text}
                 return None
            data = response.json()
            print(f"SERVER INFO: Successfully fetched data from {url}", file=sys.stderr)
            return data
        except httpx.HTTPStatusError as e:
            log_error(f"HTTP error fetching {url}: Status {e.response.status_code} - Response: {e.response.text[:200]}...")
            return None
        except httpx.RequestError as e:
            log_error(f"Network error fetching {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            log_error(f"JSON decode error fetching {url}: {e} - Response Text: {response.text[:200]}...")
            return None
        except Exception as e:
            # Catch any other unexpected errors
            log_error(f"Unexpected error during NWS request to {url}: {e}")
            traceback.print_exc(file=sys.stderr) # Print full traceback for unexpected errors
            return None

def format_alert(feature: Dict[str, Any]) -> str:
    """Format an alert feature into a readable string."""
    # Use .get() for safer access to potentially missing properties
    props = feature.get("properties", {})
    # Use .strip() to remove leading/trailing whitespace from API descriptions
    description = props.get('description', 'No description available').strip()
    instruction = props.get('instruction', 'No specific instructions provided')
    if instruction:
        instruction = instruction.strip()
    else:
        instruction = 'No specific instructions provided'

    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Certainty: {props.get('certainty', 'Unknown')}
Urgency: {props.get('urgency', 'Unknown')}
Headline: {props.get('headline', 'N/A')}
Description: {description if description else 'N/A'}
Instructions: {instruction if instruction else 'N/A'}
Effective: {props.get('effective', 'N/A')}
Expires: {props.get('expires', 'N/A')}
"""

@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    # Basic input validation
    if not isinstance(state, str) or len(state) != 2 or not state.isalpha():
        return "Error: Please provide a valid two-letter US state code (e.g., CA, NY)."

    state_upper = state.upper() # NWS API uses uppercase state codes
    url = f"{NWS_API_BASE}/alerts/active/area/{state_upper}"
    data = await make_nws_request(url)

    # Check if the request failed
    if data is None:
        return f"Error: Unable to fetch alerts for '{state_upper}' from the NWS API. Check server logs for details."

    # Check the expected structure (NWS uses GeoJSON Features)
    if not isinstance(data, dict) or "features" not in data or not isinstance(data["features"], list):
        log_error(f"Unexpected data structure received for alerts/{state_upper}: {str(data)[:200]}...")
        return f"Error: Received unexpected data format when fetching alerts for {state_upper}."

    features = data["features"]
    if not features:
        return f"No active weather alerts found for {state_upper}."

    try:
        alerts = [format_alert(feature) for feature in features]
        return f"Active Alerts for {state_upper}:\n---\n" + "\n---\n".join(alerts)
    except Exception as e:
        log_error(f"Error formatting alerts for {state_upper}: {e}")
        traceback.print_exc(file=sys.stderr)
        return f"Error: Could not format the alert data received for {state_upper}."


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # Validate lat/lon ranges (basic check)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return "Error: Invalid latitude or longitude values provided."

    # Format latitude and longitude to 4 decimal places as recommended by NWS API docs
    lat_str = f"{latitude:.4f}"
    lon_str = f"{longitude:.4f}"
    points_url = f"{NWS_API_BASE}/points/{lat_str},{lon_str}"

    points_data = await make_nws_request(points_url)

    if points_data is None:
        return f"Error: Unable to get forecast grid point for location ({lat_str}, {lon_str}). The location might be outside the US or the API might be down."
    if not isinstance(points_data, dict) or "properties" not in points_data:
         log_error(f"Unexpected data structure received from points endpoint: {str(points_data)[:200]}...")
         return f"Error: Received unexpected data format for location ({lat_str}, {lon_str})."

    properties = points_data.get("properties", {})
    forecast_url = properties.get("forecast")
    grid_id = properties.get("gridId", "N/A") # Get grid info for context
    grid_x = properties.get("gridX", "N/A")
    grid_y = properties.get("gridY", "N/A")

    if not forecast_url:
        # NWS returns a specific error structure if the point is outside the US coverage
        if points_data.get("status") == 404 or "is outside the NWS operational area" in points_data.get("detail", ""):
             return f"Error: Location ({lat_str}, {lon_str}) is outside the NWS forecast coverage area (likely outside the US)."
        log_error(f"Could not find 'forecast' URL in points data for ({lat_str}, {lon_str}). Grid: {grid_id}/{grid_x},{grid_y}. Data: {str(points_data)[:200]}...")
        return f"Error: Could not determine the specific forecast URL for location ({lat_str}, {lon_str})."

    # Get the actual forecast data
    forecast_data = await make_nws_request(forecast_url)

    if forecast_data is None:
        return f"Error: Unable to fetch the detailed forecast from {forecast_url} (Grid: {grid_id}/{grid_x},{grid_y})."
    if not isinstance(forecast_data, dict) or "properties" not in forecast_data:
        log_error(f"Unexpected data structure received from forecast endpoint: {str(forecast_data)[:200]}...")
        return f"Error: Received unexpected data format for the detailed forecast (Grid: {grid_id}/{grid_x},{grid_y})."

    periods = forecast_data.get("properties", {}).get("periods")
    if not isinstance(periods, list): # Check if periods is a list
        log_error(f"Forecast data for ({lat_str}, {lon_str}) is missing 'periods' list. Data: {str(forecast_data)[:200]}...")
        return f"Error: Forecast data received for ({lat_str}, {lon_str}) is missing the forecast periods."
    if not periods:
         return f"No forecast periods available for location ({lat_str}, {lon_str}) at this time."

    # Try to get location name from points data for context
    location_info = properties.get("relativeLocation", {}).get("properties", {})
    city = location_info.get("city", "Unknown City")
    state = location_info.get("state", "Unknown State")
    location_str = f"near {city}, {state}" if city != "Unknown City" else f"at {lat_str}, {lon_str}"

    forecasts = []
    try:
        for period in periods[:7]:  # Show a few more periods (e.g., ~3 days)
            # Use .get() for all potentially missing keys within a period
            name = period.get('name', 'Unknown Period')
            temp = period.get('temperature', 'N/A')
            temp_unit = period.get('temperatureUnit', '')
            wind_speed = period.get('windSpeed', 'N/A')
            wind_dir = period.get('windDirection', '')
            short_fcst = period.get('shortForecast', 'N/A')
            detailed_fcst = period.get('detailedForecast', 'N/A').strip()

            forecast = f"""
{name}:
  Temperature: {temp}°{temp_unit}
  Wind: {wind_speed} {wind_dir}
  Forecast: {short_fcst}
  Details: {detailed_fcst}"""
            forecasts.append(forecast)

        return f"Weather forecast {location_str}:\n---\n" + "\n---\n".join(forecasts)
    except Exception as e:
        log_error(f"Error formatting forecast periods for {location_str}: {e}")
        traceback.print_exc(file=sys.stderr)
        return f"Error: Could not format the forecast data received for {location_str}."


if __name__ == "__main__":
    print("Starting MCP Weather Server (stdio transport)...", file=sys.stderr)
    # Run the server using stdio transport
    mcp.run(transport='stdio')
    print("MCP Weather Server stopped.", file=sys.stderr)
