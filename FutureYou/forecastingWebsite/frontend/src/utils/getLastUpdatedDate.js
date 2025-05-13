export const getLastUpdatedDate = (invoices) => {
  if (!Array.isArray(invoices) || invoices.length === 0) return null;

  const latestDate = invoices.reduce((latest, invoice) => {
    const current = new Date(invoice.UpdatedDate);
    return current > latest ? current : latest;
  }, new Date(0));

  // ✅ Format to string in Australia/Sydney timezone
  return latestDate.toLocaleString("en-AU", {
    timeZone: "Australia/Sydney",
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
};
