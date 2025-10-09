def is_significant_change(old_data, new_data):
    if not old_data or not new_data:
        return True

    try:
        old_price = old_data.get("current_price")
        new_price = new_data.get("current_price")

        old_availability = old_data.get("availability")
        new_availability = new_data.get("availability")

        return old_price != new_price or old_availability != new_availability

    except:
        return True