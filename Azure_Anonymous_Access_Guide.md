# Azure Blob Storage Anonymous Access Configuration Guide

This guide will help you configure your Azure Blob Storage container for anonymous (public) access so the Streamlit app can fetch data without authentication.

## 🎯 **Step-by-Step Configuration**

### **Step 1: Access Azure Portal**
1. Go to [https://portal.azure.com](https://portal.azure.com)
2. Sign in with your Azure credentials
3. Navigate to your storage account: `sthenry1117a697874616865`

### **Step 2: Enable Anonymous Access at Storage Account Level**
1. In your storage account, look for **"Configuration"** in the left menu
2. Click on **"Configuration"**
3. Find the setting **"Allow Blob anonymous access"**
4. **Set it to "Enabled"**
5. Click **"Save"** at the top

### **Step 3: Configure Container Public Access Level**
1. In your storage account, click on **"Containers"** in the left menu
2. Find your container **"cmstest"**
3. Click on the **"cmstest"** container name (not the checkbox)
4. In the container view, click **"Change access level"** or **"Access policy"**
5. Set **"Public access level"** to one of these options:
   - **"Blob (anonymous read access for blobs only)"** ✅ **RECOMMENDED**
   - **"Container (anonymous read access for containers and blobs)"**

6. Click **"OK"** or **"Save"**

### **Step 4: Verify Anonymous Access**
Test that anonymous access is working by trying to access a file directly in your browser:

```
https://sthenry1117a697874616865.blob.core.windows.net/cmstest/hospitals_01_2022/Timely_and_Effective_Care-Hospital.csv
```

If configured correctly, this should either:
- Download the CSV file
- Show the CSV content in your browser
- Return a 404 if the file doesn't exist (but not an authentication error)

## 🚨 **If Anonymous Access Doesn't Work**

### **Alternative 1: Use SAS Token Authentication**
If you prefer to keep the container private, update your Streamlit app to use SAS token authentication:

1. **Create `.streamlit/secrets.toml`**:
```toml
[azure_blob]
account_name = "sthenry1117a697874616865"
container_name = "cmstest"
sas_token = "sp=rwl&st=2025-09-26T10:21:41Z&se=2026-09-26T18:36:41Z&spr=https&sv=2024-11-04&sr=c&sig=1tpQfgFwj9hZuME5XfD4SPv0IlP3yKfTlR6ywVPZdg8%3D"
```

2. **Update the Streamlit app** (I can do this if needed)

### **Alternative 2: Check Corporate Policies**
Some organizations have policies that prevent anonymous blob access. If you're in a corporate environment:

1. Contact your Azure administrator
2. Request permission to enable anonymous access
3. Or ask them to configure it for you

## 🔍 **Troubleshooting Common Issues**

### **Issue 1: "Allow Blob anonymous access" is Disabled**
**Solution**: 
- This might be disabled by organizational policy
- Contact your Azure administrator
- Or use SAS token authentication instead

### **Issue 2: Container Access Policy Option Missing**
**Solution**:
- Make sure you have "Storage Blob Data Contributor" role
- Try refreshing the page
- Use Azure CLI as alternative (see below)

### **Issue 3: 403 Forbidden Errors**
**Solution**:
- Verify both storage account and container settings are correct
- Check that the blob files exist in the expected locations
- Try using SAS token authentication

## 🖥️ **Alternative: Using Azure CLI**

If the portal doesn't work, you can use Azure CLI:

```bash
# Login to Azure
az login

# Enable anonymous access on storage account
az storage account update \
  --name sthenry1117a697874616865 \
  --allow-blob-public-access true

# Set container to allow anonymous access
az storage container set-permission \
  --name cmstest \
  --account-name sthenry1117a697874616865 \
  --public-access blob
```

## 📋 **Verification Checklist**

Before testing the Streamlit app, verify:

- [ ] ✅ Storage account "Allow Blob anonymous access" = **Enabled**
- [ ] ✅ Container "cmstest" public access level = **Blob** or **Container**
- [ ] ✅ Can access a test file URL in browser without authentication
- [ ] ✅ Hospital folders exist: `hospitals_01_2021`, `hospitals_01_2022`, etc.
- [ ] ✅ CSV files exist in folders: `Timely_and_Effective_Care-Hospital.csv`

## 🔐 **Security Considerations**

**Anonymous Access Means**:
- ✅ Anyone with the URL can read your blob files
- ✅ No authentication required
- ❌ Data is publicly accessible
- ❌ Consider if this meets your security requirements

**If you need security**, use SAS token authentication instead of anonymous access.

## 🚀 **Next Steps**

Once anonymous access is configured:

1. Test the direct URL access
2. Run your Streamlit app: `streamlit run streamlit_app.py`
3. Try to analyze some hospital data
4. If issues persist, check the browser's developer console for specific error messages

---

**Need Help?** If you continue to have issues, let me know the specific error messages you're seeing, and I can help troubleshoot or switch to SAS token authentication.
