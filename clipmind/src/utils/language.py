import arabic_reshaper
from bidi.algorithm import get_display

def print_urdu(text: str):
    """
    Ensures that Urdu/Arabic script is displayed correctly in terminal environments.
    Handles character reshaping and Right-to-Left (RTL) ordering.
    
    Args:
        text (str): The raw Unicode string containing Urdu text.
        
    Returns:
        str: Reordered and reshaped text ready for terminal printing.
    """
    # Fix the visual appearance of Arabic-style characters based on their position in words
    reshaped_text = arabic_reshaper.reshape(text)
    # Apply the Bidirectional (BiDi) algorithm to ensure correct LTR -> RTL flow
    bidi_text = get_display(reshaped_text)
    return bidi_text