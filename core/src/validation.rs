use serde::{Deserialize, Deserializer};
use std::str::FromStr;
use uuid::Uuid;
use chrono::DateTime;
use rust_decimal::Decimal;

/// Validates that the string is a valid UUID and returns it as a string.
pub fn deserialize_uuid<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    Uuid::parse_str(&s).map_err(serde::de::Error::custom)?;
    Ok(s)
}

/// Validates that the string is a valid RFC3339 UTC timestamp and returns it.
pub fn deserialize_rfc3339<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    DateTime::parse_from_rfc3339(&s).map_err(serde::de::Error::custom)?;
    Ok(s)
}

/// Validates that the string contains a valid decimal representation (no NaN, inf, or arbitrary characters).
pub fn deserialize_decimal_string<'de, D>(deserializer: D) -> Result<String, D::Error>
where
    D: Deserializer<'de>,
{
    let s = String::deserialize(deserializer)?;
    
    if s.is_empty() {
        return Err(serde::de::Error::custom("decimal string cannot be empty"));
    }
    
    let mut chars = s.chars().peekable();
    if chars.peek() == Some(&'-') {
        chars.next();
    }
    
    let mut has_integer_digits = false;
    let mut has_fractional_digits = false;
    let mut has_dot = false;
    
    for c in chars {
        if c == '.' {
            if has_dot {
                return Err(serde::de::Error::custom("multiple dots in decimal string"));
            }
            has_dot = true;
        } else if c.is_ascii_digit() {
            if has_dot {
                has_fractional_digits = true;
            } else {
                has_integer_digits = true;
            }
        } else {
            return Err(serde::de::Error::custom(format!("invalid character '{}' in decimal string", c)));
        }
    }
    
    if !has_integer_digits && !has_fractional_digits {
        return Err(serde::de::Error::custom("decimal string requires digits"));
    }
    
    if Decimal::from_str(&s).is_err() {
        return Err(serde::de::Error::custom("failed to parse decimal value"));
    }

    Ok(s)
}

/// Validates that the schema version is >= 1.
pub fn deserialize_schema_version<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: Deserializer<'de>,
{
    let version = u32::deserialize(deserializer)?;
    if version < 1 {
        return Err(serde::de::Error::custom("schema version must be >= 1"));
    }
    Ok(version)
}

/// Optional UUID deserialization
pub fn deserialize_opt_uuid<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let opt_s: Option<String> = Option::deserialize(deserializer)?;
    match opt_s {
        Some(s) => {
            Uuid::parse_str(&s).map_err(serde::de::Error::custom)?;
            Ok(Some(s))
        },
        None => Ok(None)
    }
}

/// Optional timestamp deserialization
pub fn deserialize_opt_rfc3339<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let opt_s: Option<String> = Option::deserialize(deserializer)?;
    match opt_s {
        Some(s) => {
            DateTime::parse_from_rfc3339(&s).map_err(serde::de::Error::custom)?;
            Ok(Some(s))
        },
        None => Ok(None)
    }
}

/// Optional decimal deserialization
pub fn deserialize_opt_decimal_string<'de, D>(deserializer: D) -> Result<Option<String>, D::Error>
where
    D: Deserializer<'de>,
{
    let opt_s: Option<String> = Option::deserialize(deserializer)?;
    match opt_s {
        Some(s) => {
            if s.is_empty() {
                return Err(serde::de::Error::custom("decimal string cannot be empty"));
            }
            if Decimal::from_str(&s).is_err() {
                return Err(serde::de::Error::custom("failed to parse decimal value"));
            }
            Ok(Some(s))
        },
        None => Ok(None)
    }
}
