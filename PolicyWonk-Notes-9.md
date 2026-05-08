To find your SharePoint site URL for integration, here are the methods:

## 1. **From SharePoint Web Interface**

Navigate to your SharePoint site and look at the browser's address bar:

```
https://[tenant-name].sharepoint.com/sites/[site-name]
```

For your diocese, it might look like:

```
https://dioceseofpensacolat.sharepoint.com/sites/Policy
```

## 2. **From the COO's Email**

The COO already provided it in their email:

```
SharePoint Site:
https://dioceseofpensacolat.sharepoint.com/sites/Policy
```

This is your `SHAREPOINT_SITE_URL` for the integration.

## 3. **From SharePoint Admin Center**

If you're an admin:

1. Go to SharePoint Admin Center
2. Click on "Active sites"
3. Find your Policy site
4. Click on the site name
5. The URL will be shown in the details panel

## 4. **From Microsoft 365 Admin Center**

1. Sign in to admin.microsoft.com
2. Go to "Resources" → "Sites"
3. Search for "Policy"
4. Click to view details

## 5. **From Teams (if connected)**

If your SharePoint site is connected to Teams:

1. Go to the Teams channel
2. Click on "Files" tab
3. Click "Open in SharePoint"
4. Copy the URL from browser

## For Your .env File:

```bash
SHAREPOINT_SITE_URL=https://dioceseofpensacolat.sharepoint.com/sites/Policy
SHAREPOINT_TENANT_ID=your-tenant-id-here
SHAREPOINT_CLIENT_ID=your-client-id-here
SHAREPOINT_CLIENT_SECRET=your-client-secret-here
```

## Important Notes:

- The URL should **not** include any page names like `/SitePages/Home.aspx`
- It should end with `/sites/[site-name]`
- For document libraries, you'll append `/_api/web/lists/getbytitle('Policy Tracker')/items`

## To Verify:

Try accessing these URLs in your browser:

1. Site: `https://dioceseofpensacolat.sharepoint.com/sites/Policy`
2. API test: `https://dioceseofpensacolat.sharepoint.com/sites/Policy/_api/web/title`

If you can access the first URL and see your Policy site, that's your correct site URL for integration!