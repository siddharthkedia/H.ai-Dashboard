import {
  Card,
  CardContent,
  Typography,
  Grid,
  Select,
  MenuItem,
  FormControl,
  Box,
  Button,
  CircularProgress,
  AppBar,
  Toolbar,
  IconButton,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputLabel,
  TextField,
} from "@mui/material";
import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import SettingsIcon from "@mui/icons-material/Settings";

const Dashboard = () => {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState();
  const [endDate, setEndDate] = useState();
  const [frequency, setFrequency] = useState("Weekly");
  const [chartData, setChartData] = useState({});
  const [rawData, setRawData] = useState([]);
  const [prevStartDate, setPrevStartDate] = useState(startDate);
  const [prevEndDate, setPrevEndDate] = useState(endDate);
  const [openSettings, setOpenSettings] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/api/metrics",
        {
          startDate: startDate,
          endDate: endDate,
        },
        {
          params: { botName: "HAiBot" },
        }
      );
      console.log("response fetched");
      const fetchedData = response.data;
      setRawData(fetchedData);
      console.log("Raw Data->", JSON.stringify(fetchedData));
      const aggregatedData = aggregateData(fetchedData, frequency);
      console.log("Aggregate Data->", JSON.stringify(aggregatedData));
      setMetrics(aggregatedData);
      setChartData(formatChartData(aggregatedData));
      setPrevStartDate(startDate);
      setPrevEndDate(endDate);
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    console.log("Clicked apply");
    if (startDate !== prevStartDate || endDate !== prevEndDate) {
      console.log("Fetching metrics");
      fetchMetrics();
    } else {
      console.log("Aggregating metrics at frontend");
      const aggregatedData = aggregateData(rawData, frequency);
      setMetrics(aggregatedData);
      setChartData(formatChartData(aggregatedData));
    }
  };

  const aggregateData = (rawData, frequency) => {
    const groupedData = {};

    rawData.forEach((metric) => {
      metric.values.forEach((entry) => {
        const date = new Date(entry.period);
        let key;

        if (frequency === "Weekly") {
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay() + 1); // Ensure week starts on Monday
          key = weekStart.toISOString().split("T")[0];
        } else if (frequency === "Monthly") {
          key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(
            2,
            "0"
          )}`;
        } else if (frequency === "Quarterly") {
          const quarter = Math.floor(date.getMonth() / 3) + 1;
          key = `${date.getFullYear()}-Q${quarter}`;
        } else if (frequency === "Yearly") {
          key = `${date.getFullYear()}`;
        }

        if (!groupedData[key]) {
          groupedData[key] = { period: key };
        }

        if (!groupedData[key][metric.metric]) {
          groupedData[key][metric.metric] = 0;
        }

        groupedData[key][metric.metric] += entry.value;
      });
    });

    return Object.values(groupedData);
  };

  // Format Data for Charts (Separate Data for Each Metric)
  const formatChartData = (aggregatedData) => {
    const formattedData = {};
    if (aggregatedData.length === 0) return formattedData;

    Object.keys(aggregatedData[0]).forEach((metric) => {
      if (metric !== "period") {
        formattedData[metric] = aggregatedData.map((entry) => ({
          period: entry.period,
          value: entry[metric] || 0,
        }));
      }
    });

    return formattedData;
  };

  return (
    <Box sx={{ flexGrow: 1}}>
      <AppBar position="static" sx={{ backgroundColor: "#47ee3f" }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Dashboard Metrics
          </Typography>
          <IconButton color="inherit" onClick={() => setOpenSettings(true)}>
            <SettingsIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Dialog open={openSettings} onClose={() => setOpenSettings(false)}>
        <DialogTitle>Settings</DialogTitle>
        <DialogContent>
          <FormControl fullWidth margin="normal">
            <TextField
              type="date"
              label="Start Date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </FormControl>
          <FormControl fullWidth margin="normal">
            <TextField
              type="date"
              label="End Date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </FormControl>
          <FormControl fullWidth margin="normal">
            <InputLabel>Frequency</InputLabel>
            <Select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
            >
              <MenuItem value="Weekly">Weekly</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenSettings(false)}>Cancel</Button>
          <Button onClick={() => {handleApply(); setOpenSettings(false);}} variant="contained" color="primary">
            Apply
          </Button>
        </DialogActions>
      </Dialog>

      <Box padding={3} bgcolor="#f4f4f4">
        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" height="50vh">
            <CircularProgress />
          </Box>
        ) : (
          <>
            <Grid container spacing={2} marginTop={2}>
              {Object.keys(chartData).map((metric, index) => (
              <Grid item xs={12} sm={6} md={4} lg={4} key={index} sx={{ minWidth: "30% " }}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ flexGrow: 1 }}>
                      <Typography variant="h6" gutterBottom fontWeight="bold">
                        {metric}
                      </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Total: {metrics.reduce((sum, entry) => sum + (entry[metric] || 0), 0)}
                    </Typography>
                    <ResponsiveContainer width="100%" height="80%">
                        <LineChart data={chartData[metric]}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#8884d8"
                            strokeWidth={2}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </>
        )}
      </Box>
    </Box>
  );
};

export default Dashboard;