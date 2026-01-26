# Receipts Directory

Place your receipt images here for processing.

## Supported Formats

- PNG (.png)
- JPEG (.jpg, .jpeg)
- Other image formats supported by PIL

## Tips for Best Results

1. **Image Quality**
   - Use high-resolution images (1000px+ width)
   - Ensure text is clearly readable
   - Avoid blurry or low-quality scans

2. **Lighting**
   - Good, even lighting
   - Avoid shadows or glare
   - Don't overexpose (all white) or underexpose (too dark)

3. **Alignment**
   - Keep receipt straight (not tilted)
   - Capture the entire receipt
   - Avoid cutting off edges

4. **Background**
   - Plain, contrasting background works best
   - Remove clutter around the receipt

## Example

To test the service, add your receipt images:

```bash
# Copy your receipt
cp ~/Downloads/receipt.jpg .

# Or take a photo and transfer it here
```

Then run:

```bash
python ../test_api.py your_receipt.jpg
```
