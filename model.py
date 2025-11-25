# Schema definitions for restaurant detail extraction results
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class Address(BaseModel):
    street: Optional[str] = Field(None, description="Street name and number")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State or province")
    postal_code: Optional[str] = Field(None, description="ZIP or postal code")
    country: Optional[str] = Field(None, description="Country name")
    full_address: Optional[str] = Field(
        None, 
        description="The full address as extracted if not easily separable"
    )


class HoursOfOperation(BaseModel):
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None
    notes: Optional[str] = Field(
        None, 
        description="Any notes such as holiday hours, brunch-only, etc."
    )


class SocialLinks(BaseModel):
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter_x: Optional[str] = Field(None, alias="twitter")
    tiktok: Optional[str] = None
    opentable: Optional[str] = None
    yelp: Optional[str] = None
    google_maps: Optional[str] = None


class MenuItem(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[str] = None


class MenuCategory(BaseModel):
    """
    A category within a section.
    e.g., "Antipasti", "Pizza", "Pasta"
    """
    category_name: str
    items: List[MenuItem]


class MenuSection(BaseModel):
    """
    A full menu section, e.g., "Lunch", "Dinner", "Dessert".
    Each section contains its own categories.
    """
    section_name: str
    categories: List[MenuCategory]


class Menu(BaseModel):
    """
    The full restaurant menu.
    For restaurants with multiple menu pages or subsections.
    """
    restaurant_name: Optional[str] = None
    sections: List[MenuSection]


class RestaurantInfo(BaseModel):
    restaurant_name: Optional[str] = Field(None, description="Full restaurant name")
    phone_number: Optional[str] = None
    email: Optional[str] = None

    address: Optional[Address] = None
    hours: Optional[HoursOfOperation] = None

    menu: Optional[Menu] = None

    social_links: Optional[SocialLinks] = None
    description: Optional[str] = Field(
        None, 
        description="Short blurb or summary about the restaurant from the website"
    )

    additional_info: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Any extra extracted details that do not fit standard fields"
    )

