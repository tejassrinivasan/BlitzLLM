import React from 'react';
import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate, useParams, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LineChart, Line, BarChart, Bar, ScatterChart, Scatter, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import ShareModal from './ShareModal';
import UpcomingGamesTicker from './UpcomingGamesTicker';
import blitzLogo from '../images/blitz.png';
import defaultPlayerImage from '../images/default.jpg';
import JsxParser from 'react-jsx-parser';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm'; // <<< Import remark-gfm
import rehypeRaw from 'rehype-raw';
import { debounce } from 'lodash';
import { toPng } from 'html-to-image';
import { format, isSameDay, addDays } from 'date-fns';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL;

// Add this constant at the top of the file
const TASK_TIMEOUT_MS = 100000; // 100 seconds

// Add this function at the top of your component or in a utility file
const cleanMessageContent = (inputRef) => {
  // Check if inputRef and inputRef.current exist before proceeding
  if (!inputRef || !inputRef.current) {
    return '';
  }
  console.log("[cleanMessageContent] Original input HTML:", inputRef.current.innerHTML); // Log original HTML
  
  // Clone the input element to avoid modifying the actual DOM
  const clone = inputRef.current.cloneNode(true);
  
  // Remove any mention tags or other special elements if needed
  const mentionTags = clone.querySelectorAll('.mention-tag');
  console.log(`[cleanMessageContent] Found ${mentionTags.length} mention tags.`); // Log tag count
  mentionTags.forEach((tag, index) => {
    // Get the value, prioritizing dataset.value
    let value = tag.dataset.value || tag.textContent;
    console.log(`[cleanMessageContent] Tag ${index} original value:`, value); // Log original value
    // Remove the leading '@' if it exists
    if (value.startsWith('@')) {
      value = value.substring(1);
      console.log(`[cleanMessageContent] Tag ${index} cleaned value:`, value); // Log cleaned value
    }
    // Replace the tag with the cleaned text value
    const textNode = document.createTextNode(value);
    tag.parentNode.replaceChild(textNode, tag);
  });
  
  // Return the cleaned text content
  const cleaned = clone.textContent.trim();
  console.log("[cleanMessageContent] Final cleaned text:", cleaned); // Log final text
  return cleaned;
};

// Helper to remove duplicate messages by id
const deduplicateMessages = (messages) => {
  const seen = new Set();
  return messages.filter(msg => {
    if (seen.has(msg.id)) return false;
    seen.add(msg.id);
    return true;
  });
};

// Add this helper function at the top level
const MAX_STORED_MESSAGES = 50; // Adjust this number based on your needs
const limitMessages = (messages) => {
  if (!messages || !Array.isArray(messages)) return [];
  return messages.slice(-MAX_STORED_MESSAGES);
};

const safeSetItem = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    // If we hit quota, clear old message caches
    if (err.name === 'QuotaExceededError') {
      const keys = Object.keys(localStorage);
      const messageCacheKeys = keys.filter(k => k.startsWith('messages_'));
      // Remove old message caches
      messageCacheKeys.forEach(k => localStorage.removeItem(k));
      // Try setting the item again
      try {
        localStorage.setItem(key, value);
      } catch (retryErr) {
        console.warn('Still unable to set localStorage item after cleanup');
      }
    }
  }
};

// Utility to remove backticks around any HTML tag, even if there is other text inside
function removeFontBackticks(content) {
  if (!content) return content;
  // Replace any backtick-wrapped content that contains an HTML tag, removing the backticks
  return content.replace(/`([^`]*<([a-zA-Z0-9]+)[^>]*>.*?<\/\2>[^`]*)`/g, '$1');
}

function Chat() {
  const [conversations, setConversations] = useState([]);
  const [currentMessages, setCurrentMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [editingMessageId, setEditingMessageId] = useState(null);
  const [editingMessageContent, setEditingMessageContent] = useState('');
  const [isStoppingResponse, setIsStoppingResponse] = useState(false);
  const messagesEndRef = useRef(null);
  const messageRefs = useRef({});
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const chatContainerRef = useRef(null);
  const [screenshotUrl, setScreenshotUrl] = useState('');
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [sidebarWidth, setSidebarWidth] = useState(256);
  const [isResizing, setIsResizing] = useState(false);
  const { token, refreshUserInfo } = useAuth();
  const [helpfulStates, setHelpfulStates] = useState({});
  const [unhelpfulStates, setUnhelpfulStates] = useState({});
  const [pendingMessage, setPendingMessage] = useState('');
  const [sendingMessages, setSendingMessages] = useState({});
  const [mentions, setMentions] = useState([]);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const [isMentioning, setIsMentioning] = useState(false);
  const mentionStartIndex = useRef(0);
  const [localMentions, setLocalMentions] = useState([]);
  const previousQuery = useRef('');
  const inputRef = useRef(null);
  const [retryErrors, setRetryErrors] = useState({});
  const [allMentions, setAllMentions] = useState([]);
  const [isLoadingMentions, setIsLoadingMentions] = useState(true);
  const [currentStep, setCurrentStep] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [showSteps, setShowSteps] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState(null);
  const [isCurrentConversation, setIsCurrentConversation] = useState(false);
  const [editingContent, setEditingContent] = useState('');
  const editInputRef = useRef(null);
  const [displayedQuestions, setDisplayedQuestions] = useState([]);
  const [selectedGameId, setSelectedGameId] = useState(null);
  const [isTransitioningQuestions, setIsTransitioningQuestions] = useState(false);

  // Add the full question bank
  const questionBank = [
    "Percent of games where Aaron Judge hits a home run and Yankees win the game?",
    "Show me the mean, median, and middle 50% of runs scored by the Cubs, by year?",
    "What percent of the time do all of the first 3 batters on a team get a run and the team loses?",
    "Against which team does Juan Soto have the most hits?",
    "What was the largest margin of victory so far this month?",
    "How many times have the Dodgers been favorites in 2025?",
    "What's the average number of strikeouts per game for Logan Gilbert this season?",
    "How many times has Shohei Ohtani hit a home run and pitched in the same game?",
    "Who hit the most home runs in 2023?",
    "What percent of the time time does a starting pitcher finish with 100+ pitches and the team loses?",
    "Show me last 10 game trends for Bryce Harper"
  ];

  // Function to shuffle and get 4 random questions
  const shuffleQuestions = useCallback(() => {
    const shuffled = [...questionBank].sort(() => Math.random() - 0.5);
    setDisplayedQuestions(shuffled.slice(0, 4));
  }, []);

  const handleGameSelect = (game) => {
    if (!game) return;
    setSelectedGameId(game.GameID);
    setIsTransitioningQuestions(true);
    setTimeout(() => {
      const { AwayTeam, HomeTeam, Day } = game;
      console.log("Game:", game);
      // List of all possible questions
      const formattedDate = new Date(Day).toLocaleDateString('en-US', {
        month: 'numeric',
        day: 'numeric',
        year: 'numeric'
      });
      const allQuestions = [
        // `What are the highest EV bets for the upcoming ${AwayTeam} vs ${HomeTeam} matchup on ${formattedDate}`,
        `What are the recent team performance trends for ${AwayTeam} and ${HomeTeam}`,
        // `What prop or game props have hit frequently in the past in a ${AwayTeam} vs ${HomeTeam} matchup`,
        `Break down the last 10 games between ${AwayTeam} and ${HomeTeam}`,
        `Show each teams record as a favorite / underdog this year for both ${AwayTeam} and ${HomeTeam}`,
        `Who is most likely to get a home run in the upcoming ${AwayTeam} vs ${HomeTeam} matchup on ${formattedDate}`,
        `Breakdown key players projections in the upcoming ${AwayTeam} vs ${HomeTeam} matchup on ${formattedDate}`
      ];
      
      // Randomly select 4 questions
      const shuffled = [...allQuestions].sort(() => 0.5 - Math.random());
      const selectedQuestions = shuffled.slice(0, 4);
      
      setDisplayedQuestions(selectedQuestions);
      setIsTransitioningQuestions(false);
    }, 200); // fade out, then in
  };

  const handleShuffleQuestions = useCallback(() => {
    setIsTransitioningQuestions(true);
    setTimeout(() => {
      shuffleQuestions();
      setSelectedGameId(null);
      setIsTransitioningQuestions(false);
    }, 200);
  }, [shuffleQuestions]);

  // Initialize questions on component mount
  useEffect(() => {
    shuffleQuestions();
  }, [shuffleQuestions]);

  // Add this to the useEffect that injects the style tag
  useEffect(() => {
    const styleTag = document.createElement('style');
    styleTag.textContent = `
      @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
      }
      
      @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(-10px); }
      }

      @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
      }
      
      .step-transition {
        animation: fadeIn 0.3s ease-out forwards;
      }
      
      .step-transition.fade-out {
        animation: fadeOut 0.3s ease-out forwards;
      }

      .pulse-animation {
        animation: pulse 2s ease-in-out infinite;
      }
    `;
    document.head.appendChild(styleTag);
    return () => styleTag.remove();
  }, []);

  // Fetch conversations list
  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/conversations`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          setConversations(data);
        }
      } catch (error) {
        console.error('Error fetching conversations:', error);
      }
    };

    fetchConversations();
  }, [token]);

  // Fetch messages for current conversation
  useEffect(() => {
    const fetchMessages = async () => {
      if (!conversationId) return;

      try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          console.log("Fetched messages:", data);
          if (data.length === 0 && pendingMessage) {
            // If no messages yet and we have pending message, show temporary message
            const tempUserMessage = {
              id: `temp-${Date.now()}`,
              role: 'user',
              content: pendingMessage,
              created_at: new Date().toISOString(),
              is_temporary: true
            };
            setCurrentMessages([tempUserMessage]);
          } else {
            // Process messages to ensure error fields are properly set
            const processedMessages = data.map(msg => ({
              ...msg,
              is_error: msg.is_error || (msg.error_message && msg.error_message.length > 0),
              error_message: msg.error_message || null
            }));
            setCurrentMessages(deduplicateMessages(processedMessages));
          }
        }
      } catch (error) {
        console.error('Error fetching messages:', error);
      }
    };

    fetchMessages();
  }, [conversationId, token, pendingMessage]);

  // Modify the scroll to bottom behavior to be less aggressive
  useEffect(() => {
    if (messagesEndRef.current) {
      // Use a smoother scroll that doesn't force the navbar out of view
      messagesEndRef.current.scrollIntoView({ 
        behavior: 'smooth',
        block: 'end' // This ensures we only scroll as much as needed
      });
    }
  }, [currentMessages]);

  // Modify the scroll to bottom useEffect
  useEffect(() => {
    if (messagesEndRef.current) {
      // Force scroll to bottom on page load/refresh
      const scrollContainer = chatContainerRef.current;
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [currentMessages]); // Keep the dependency on currentMessages

  const [isNewChatLoading, setIsNewChatLoading] = useState(false);

  // Modify handleSubmit to use the cleaned content AND clear inputRef
  const handleSubmit = async (e) => {
    e.preventDefault();
    // Check based on raw content first
    const rawContent = inputRef.current ? inputRef.current.textContent : inputMessage;
    if (!rawContent.trim() || sendingMessages[conversationId] || !conversationId) return;

    // Use the input message directly if inputRef is not available
    const cleanedMessage = inputRef.current ? cleanMessageContent(inputRef) : inputMessage.trim();
    console.log("[handleSubmit] Cleaned message to send:", cleanedMessage);

    setInputMessage('');
    if (inputRef.current) {
        inputRef.current.innerHTML = '';
        inputRef.current.classList.add('empty');
    }

    // Get current messages for history
    const history = currentMessages.map(msg => ({
        role: msg.role,
        content: msg.content
    }));

    // If we're editing a message, remove it and all subsequent messages
    if (editingMessageId) {
        const editIndex = currentMessages.findIndex(msg => msg.id === editingMessageId);
        if (editIndex !== -1) {
            // Remove the edited message and all messages after it
            setCurrentMessages(prev => prev.slice(0, editIndex));
            setEditingMessageId(null);
            setEditingMessageContent('');
        }
    }

    // Immediately add the user's message to the UI
    const userMessage = {
        role: 'user',
        content: cleanedMessage,
        id: 'temp-' + Date.now(),
        created_at: new Date().toISOString(),
        is_temporary: true
    };
    setCurrentMessages(prev => [...prev, userMessage]);

    try {
        setSendingMessages(prev => ({ ...prev, [conversationId]: true }));
        setIsStreaming(true);

        // Start the task
        const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages/stream`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: cleanedMessage,
                generate_title: currentMessages.length === 0,
                history
            })
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        const { task_id } = await response.json();
        
        // Store task info and user message in localStorage
        localStorage.setItem(`task_${conversationId}`, JSON.stringify({
          taskId: task_id,
          timestamp: Date.now(),
          userMessage: cleanedMessage,
          conversationId: parseInt(conversationId)
        }));
        setActiveTaskId(task_id);

        // Poll for task status
        while (true) {
            const statusResponse = await fetch(`${API_BASE_URL}/api/tasks/${task_id}`);
            const taskStatus = await statusResponse.json();
            
            if (taskStatus.status === 'not_found') {
                throw new Error('Task not found');
            }
            
            // Update current step
            if (taskStatus.step) {
                setCurrentStep(taskStatus.step);
            }
            
            if (taskStatus.status === 'complete') {
                // Update messages and title
                setCurrentMessages(prev => {
                    const filtered = prev.filter(msg => msg.id !== userMessage.id);
                    return [...filtered, taskStatus.user_message, taskStatus.assistant_message];
                });
                
                if (taskStatus.title) {
                    setConversations(prev => 
                        prev.map(conv => 
                            conv.id === parseInt(conversationId)
                                ? { ...conv, title: taskStatus.title }
                                : conv
                        )
                    );
                }
                localStorage.removeItem(`task_${conversationId}`);
                setIsStreaming(false);
                setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
                setActiveTaskId(null);
                break;
            } else if (taskStatus.status === 'clarification_needed') {
              // Fetch latest messages and update the chat
              const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
                headers: { 'Authorization': `Bearer ${token}` }
              });
              if (response.ok) {
                const data = await response.json();
                setCurrentMessages(deduplicateMessages(data));
              }
              setIsStreaming(false);
              setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
              localStorage.removeItem(`task_${conversationId}`);
              setActiveTaskId(null);
              break;
            } else if (taskStatus.status === 'error') {
                throw new Error(taskStatus.error);
            }
            
            // Wait before next poll
            await new Promise(resolve => setTimeout(resolve, 1000));
        }

    } catch (error) {
        console.error('Error sending message:', error);
        // Keep the user message and add an error message
        setCurrentMessages(prev => {
            const filtered = prev.filter(msg => msg.id !== userMessage.id);
            return [...filtered, userMessage, {
                id: `error-${Date.now()}`,
                role: 'assistant',
                content: error.message,
                created_at: new Date().toISOString(),
                is_error: true,
                error_message: error.message
            }];
        });
        localStorage.removeItem(`task_${conversationId}`);
        setActiveTaskId(null);
    } finally {
        setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
        setIsStreaming(false);
        setCurrentStep('');
    }
};

  const handleDeleteConversation = async (id) => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete conversation');
      }
      
      // Update the conversations list
      setConversations(prev => prev.filter(conv => conv.id !== id));
      
      // If the deleted conversation was the current one, navigate back to chat home
      if (id === parseInt(conversationId)) {
        navigate('/chat');
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
      // Add error notification here if you want
    }
  };

  const handleNewChat = async () => {
    // Check based on raw content first
    const rawContent = inputRef.current ? inputRef.current.textContent : inputMessage;
    if (!rawContent.trim()) return;

    const messageText = inputRef.current ? cleanMessageContent(inputRef) : inputMessage.trim();
    console.log("[handleNewChat] Cleaned message to send (messageText):", messageText);

    setInputMessage('');
    if (inputRef.current) {
        inputRef.current.innerHTML = '';
        inputRef.current.classList.add('empty');
    }
    setPendingMessage(messageText);

    let newConversationId = null;

    try {
      setIsNewChatLoading(true);
      setIsStreaming(true);
      setShowSteps(true);

      // Create new conversation
      const response = await fetch(`${API_BASE_URL}/api/conversations`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to create new conversation');
      }

      const data = await response.json();
      newConversationId = data.id;

      // Add temporary user message immediately
      const tempUserMessage = {
        role: 'user',
        content: messageText,
        id: `temp-${Date.now()}`,
        created_at: new Date().toISOString(),
        is_temporary: true
      };

      // Set UI state BEFORE navigation
      setSendingMessages(prev => ({ ...prev, [newConversationId]: true }));
      setCurrentMessages([tempUserMessage]);
      setConversations(prev => [{ ...data, title: 'New Chat' }, ...prev]);

      // Start the task BEFORE navigation
      const messageResponse = await fetch(`${API_BASE_URL}/api/conversations/${newConversationId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: messageText,
          generate_title: true
        })
      });

      if (!messageResponse.ok) {
        throw new Error('Failed to send message');
      }

      const { task_id } = await messageResponse.json();
      
      // Store task info in localStorage BEFORE navigation
      localStorage.setItem(`task_${newConversationId}`, JSON.stringify({
        taskId: task_id,
        timestamp: Date.now(),
        userMessage: messageText,
        conversationId: newConversationId,
        isNewChat: true
      }));

      // Set active task ID BEFORE navigation
      setActiveTaskId(task_id);

      // Navigate to new chat AFTER everything is set up
      navigate(`/chat/${newConversationId}`);

    } catch (error) {
      console.error('Error creating new chat:', error);
      setPendingMessage('');
      if (newConversationId) {
        localStorage.removeItem(`task_${newConversationId}`);
        setSendingMessages(prev => ({ ...prev, [newConversationId]: false }));
      }
      setIsStreaming(false);
      setShowSteps(false);
    } finally {
      setIsNewChatLoading(false);
    }
  };

  const handleTwitterShare = async () => {
    try {
      // Convert data URL to blob
      const response = await fetch(screenshotUrl);
      const blob = await response.blob();

      // Create form data
      const formData = new FormData();
      formData.append('image', blob, 'screenshot.png');

      // Upload image
      const uploadResponse = await fetch(`${API_BASE_URL}/api/upload-image`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!uploadResponse.ok) {
        throw new Error('Failed to upload image');
      }

      const { imageUrl } = await uploadResponse.json();

      // Open X share dialog
      const xUrl = `https://x.com/intent/post?text=${encodeURIComponent(
        'Check out these sports analytics insights from Blitz!\n\n'
      )}&url=${encodeURIComponent(imageUrl)}`;
      window.open(xUrl, '_blank');
    } catch (error) {
      console.error('Error sharing to X:', error);
    }
  };

  const handleCopyImage = async () => {
    try {
      const response = await fetch(screenshotUrl);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({
          'image/png': blob
        })
      ]);
      // Could add a success toast here
    } catch (error) {
      console.error('Error copying image:', error);
    }
  };

  const handleSort = (key) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig.key === key && prevConfig.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const sortData = (data, key) => {
    if (!key) return data;

    return [...data].sort((a, b) => {
      let aVal = a[key];
      let bVal = b[key];

      // Convert to numbers if possible
      if (!isNaN(aVal) && !isNaN(bVal)) {
        aVal = Number(aVal);
        bVal = Number(bVal);
      }

      if (sortConfig.direction === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
      } else {
        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
      }
    });
  };

  const handleShare = async (messageElement) => {
    try {
      if (messageElement) {
        // Clone the original message element
        const cloneForScreenshot = messageElement.cloneNode(true);
        
        // Remove share buttons and any other UI elements we don't want in the screenshot
        const shareButtons = cloneForScreenshot.querySelectorAll('button');
        shareButtons.forEach(button => button.remove());

        // Get original dimensions and styles
        const originalStyles = window.getComputedStyle(messageElement);
        const { width } = messageElement.getBoundingClientRect();

        // Create wrapper with original styling - make background darker
        const wrapper = document.createElement('div');
        wrapper.style.cssText = `
          position: relative;
          width: ${width}px;
          background-color: rgb(10, 10, 10);
          border-radius: 1rem;
          overflow: hidden;
          padding: ${originalStyles.padding};
        `;

        // Create Blitz logo element
        const logoImg = document.createElement('img');
        logoImg.src = blitzLogo;
        logoImg.alt = "Blitz";
        logoImg.style.cssText = `
          height: 20px;
          width: auto;
          float: right;
          margin-left: 8px;
          margin-bottom: 4px;
        `;
        
        // Insert logo at the beginning of the content
        if (cloneForScreenshot.firstChild) {
          cloneForScreenshot.insertBefore(logoImg, cloneForScreenshot.firstChild);
        } else {
          cloneForScreenshot.appendChild(logoImg);
        }

        // Apply original styles to clone
        cloneForScreenshot.style.cssText = `
          transform: none;
          margin: 0;
          padding: ${originalStyles.padding};
          background-color: ${originalStyles.backgroundColor};
          color: ${originalStyles.color};
          font-family: ${originalStyles.fontFamily};
          font-size: ${originalStyles.fontSize};
          line-height: ${originalStyles.lineHeight};
        `;

        // Assemble the elements
        wrapper.appendChild(cloneForScreenshot);

        // Create temporary container
        const tempContainer = document.createElement('div');
        tempContainer.style.cssText = `
          position: fixed;
          top: 0;
          left: 0;
          opacity: 0;
          pointer-events: none;
          z-index: -1;
        `;
        tempContainer.appendChild(wrapper);
        document.body.appendChild(tempContainer);

        // Use html-to-image instead of html2canvas
        const dataUrl = await toPng(wrapper, {
          backgroundColor: '#0a0a0a', // Darker background
          pixelRatio: 2, // Higher scale for better quality
          cacheBust: true,
        });

        // Clean up
        document.body.removeChild(tempContainer);

        // Set result
        setScreenshotUrl(dataUrl);
        setIsShareModalOpen(true);
      }
    } catch (error) {
      console.error('Error generating screenshot:', error);
    }
  };

  // Group conversations by league
  const groupedConversations = useMemo(() => {
    return conversations.reduce((acc, conv) => {
      // Extract league from the first word of the query or title
      let league = 'Other';
      if (conv.title) {
        // Check for common sports leagues
        const title = conv.title.toLowerCase();
        if (title.includes('mlb') || title.includes('baseball')) league = 'MLB';
        else if (title.includes('nba') || title.includes('basketball')) league = 'NBA';
        else if (title.includes('nfl') || title.includes('football')) league = 'NFL';
        else if (title.includes('nhl') || title.includes('hockey')) league = 'NHL';
      }
      if (!acc[league]) acc[league] = [];
      acc[league].push(conv);
      return acc;
    }, {});
  }, [conversations]);

  // Add handlers for the sidebar icons
  const handleSidebarClose = () => {
    setIsSidebarOpen(false);
  };

  const handleSearchToggle = () => {
    setIsSearching(!isSearching);
    if (!isSearching) {
      setTimeout(() => {
        const searchInput = document.querySelector('input[type="text"]');
        if (searchInput) searchInput.focus();
      }, 100);
    }
  };

  const handleNewChatClick = () => {
    setInputMessage('');
    setCurrentMessages([]); // Clear current messages
    navigate('/chat'); // Just navigate to /chat
  };

  const handleUpdateTitle = async (conversationId, newTitle, shouldExitEdit = true) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/title`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ title: newTitle })
      });

      if (response.ok) {
        setConversations(prev => 
          prev.map(conv => 
            conv.id === parseInt(conversationId) 
              ? { ...conv, title: newTitle }
              : conv
          )
        );
        // Only exit edit mode if explicitly requested
        if (shouldExitEdit) {
          setIsEditing(false);
          setEditingId(null);
        }
      }
    } catch (error) {
      console.error('Error updating title:', error);
    }
  };

  // Add this new useEffect for handling resize
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing) return;
      
      // Use requestAnimationFrame for smoother resizing
      requestAnimationFrame(() => {
        const newWidth = Math.min(Math.max(e.clientX, 150), 600);
        setSidebarWidth(newWidth);
      });
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  const handleToggleHelpful = async (msgIndex) => {
    const currentState = helpfulStates[msgIndex] || {};
    const isCurrentlyHelpful = currentState.isHelpful === true;
    const docId = currentState.docId || null;
    
    try {
      const assistantMessage = currentMessages[msgIndex];
      const userMessage = currentMessages[msgIndex - 1];
      
      if (!assistantMessage?.id) {
        console.error("No message ID found:", assistantMessage);
        return;
      }

      // Extract SQL query from postgresql_query
      let sqlQuery = "";
      try {
        if (assistantMessage.postgresql_query) {
          const queryData = typeof assistantMessage.postgresql_query === 'string' 
            ? JSON.parse(assistantMessage.postgresql_query) 
            : assistantMessage.postgresql_query;
          sqlQuery = queryData.query?.sqlQuery || "";
        }
      } catch (error) {
        console.error("Error parsing postgresql_query:", error);
      }

      // Update local state first for immediate feedback
      setHelpfulStates(prev => ({
        ...prev,
        [msgIndex]: { 
          ...prev[msgIndex],
          isHelpful: !isCurrentlyHelpful
        }
      }));

      const messageId = Number(assistantMessage.id);
      if (isNaN(messageId)) {
        throw new Error('Invalid message ID');
      }

      // Update both feedback and helpful document
      const [feedbackResponse, helpfulResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/messages/${messageId}/feedback`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            feedback: !isCurrentlyHelpful
          })
        }),
        
        fetch(`${API_BASE_URL}/api/helpful`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            helpful: !isCurrentlyHelpful,
            doc_id: docId,
            userPrompt: userMessage?.content || "",
            sqlQuery: sqlQuery,
            message_id: messageId
          })
        })
      ]);

      if (!feedbackResponse.ok || !helpfulResponse.ok) {
        setHelpfulStates(prev => ({
          ...prev,
          [msgIndex]: { 
            ...prev[msgIndex],
            isHelpful: isCurrentlyHelpful
          }
        }));
        
        const errorData = !feedbackResponse.ok 
          ? await feedbackResponse.json() 
          : await helpfulResponse.json();
        throw new Error(JSON.stringify(errorData));
      }

      const helpfulData = await helpfulResponse.json();
      if (helpfulData.status === "created" || helpfulData.status === "exists") {
        setHelpfulStates(prev => ({
          ...prev,
          [msgIndex]: { 
            ...prev[msgIndex],
            isHelpful: true,
            docId: helpfulData.doc_id,
            sqlQuery: sqlQuery
          }
        }));
      } else if (helpfulData.status === "deleted") {
        setHelpfulStates(prev => ({
          ...prev,
          [msgIndex]: { 
            ...prev[msgIndex],
            isHelpful: false,
            docId: null,
            sqlQuery: sqlQuery
          }
        }));
      }
    } catch (error) {
      console.error("Error toggling helpful:", error);
      // Now currentState is accessible here
      setHelpfulStates(prev => ({
        ...prev,
        [msgIndex]: { 
          ...prev[msgIndex],
          isHelpful: currentState.isHelpful
        }
      }));
    }
  };

  const handleToggleUnhelpful = async (msgIndex) => {
    const currentState = unhelpfulStates[msgIndex] || {};
    const isCurrentlyUnhelpful = currentState.isUnhelpful === true;
    const docId = currentState.docId || null;

    try {
      const assistantMessage = currentMessages[msgIndex];
      const userMessage = currentMessages[msgIndex - 1];

      if (!assistantMessage?.id) {
        console.error("No message ID found:", assistantMessage);
        return;
      }

      let sqlQuery = "";
      try {
        if (assistantMessage.postgresql_query) {
          const queryData = typeof assistantMessage.postgresql_query === 'string'
            ? JSON.parse(assistantMessage.postgresql_query)
            : assistantMessage.postgresql_query;
          sqlQuery = queryData.query?.sqlQuery || "";
        }
      } catch (error) {
        console.error("Error parsing postgresql_query:", error);
      }

      setUnhelpfulStates(prev => ({
        ...prev,
        [msgIndex]: {
          ...prev[msgIndex],
          isUnhelpful: !isCurrentlyUnhelpful
        }
      }));

      const messageId = Number(assistantMessage.id);
      if (isNaN(messageId)) {
        throw new Error('Invalid message ID');
      }

      const [feedbackResponse, unhelpfulResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/messages/${messageId}/feedback`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            feedback: false
          })
        }),

        fetch(`${API_BASE_URL}/api/unhelpful`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            unhelpful: !isCurrentlyUnhelpful,
            doc_id: docId,
            userPrompt: userMessage?.content || "",
            sqlQuery: sqlQuery,
            message_id: messageId
          })
        })
      ]);

      if (!feedbackResponse.ok || !unhelpfulResponse.ok) {
        setUnhelpfulStates(prev => ({
          ...prev,
          [msgIndex]: {
            ...prev[msgIndex],
            isUnhelpful: isCurrentlyUnhelpful
          }
        }));

        const errorData = !feedbackResponse.ok
          ? await feedbackResponse.json()
          : await unhelpfulResponse.json();
        throw new Error(JSON.stringify(errorData));
      }

      const unhelpfulData = await unhelpfulResponse.json();
      if (unhelpfulData.status === "created" || unhelpfulData.status === "exists") {
        setUnhelpfulStates(prev => ({
          ...prev,
          [msgIndex]: {
            ...prev[msgIndex],
            isUnhelpful: true,
            docId: unhelpfulData.doc_id,
            sqlQuery: sqlQuery
          }
        }));
      } else if (unhelpfulData.status === "deleted") {
        setUnhelpfulStates(prev => ({
          ...prev,
          [msgIndex]: {
            ...prev[msgIndex],
            isUnhelpful: false,
            docId: null,
            sqlQuery: sqlQuery
          }
        }));
      }
    } catch (error) {
      console.error("Error toggling unhelpful:", error);
      setUnhelpfulStates(prev => ({
        ...prev,
        [msgIndex]: {
          ...prev[msgIndex],
          isUnhelpful: currentState.isUnhelpful
        }
      }));
    }
  };

  // Modify the useEffect that initializes helpful states
  useEffect(() => {
    const initialHelpfulStates = {};
    const initialUnhelpfulStates = {};
    currentMessages.forEach((message, index) => {
      if (message.role === 'assistant') {
        console.log("Initializing helpful state for message:", message);
        
        let sqlQuery = "";

        // Convert feedback to boolean, handling both string and boolean values
        const feedback = message.feedback === true || message.feedback === 'true';
        console.log("Message feedback value:", message.feedback, "Converted to:", feedback);
        
        initialHelpfulStates[index] = {
          isHelpful: feedback,
          docId: null,
          sqlQuery: sqlQuery
        };

        initialUnhelpfulStates[index] = {
          isUnhelpful: false,
          docId: null,
          sqlQuery: sqlQuery
        };
      }
    });
    console.log("Initial helpful states:", initialHelpfulStates);
    setHelpfulStates(initialHelpfulStates);
    setUnhelpfulStates(initialUnhelpfulStates);
  }, [currentMessages]);

  // Modify the searchMentions function
  const searchMentions = useCallback(
    debounce(async (query) => {
      // Don't search if query is same as previous or too short
      if (query === previousQuery.current || query.length < 2) return;
      previousQuery.current = query;

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/mentions/search?query=${encodeURIComponent(query)}`,
          {
            headers: {
              Authorization: `Bearer ${token}`
            }
          }
        );
        if (!response.ok) throw new Error('Failed to fetch mentions');
        const data = await response.json();
        
        // Ensure data is an array
        const mentions = Array.isArray(data) ? data : [];
        setMentions(mentions);
        
        // Only cache if we got results
        if (mentions.length > 0) {
          setLocalMentions(prev => {
            const newMentions = [...prev];
            mentions.forEach(mention => {
              if (!newMentions.some(m => m.id === mention.id)) {
                newMentions.push(mention);
              }
            });
            return newMentions;
          });
        }
      } catch (error) {
        console.error('Error searching mentions:', error);
        setMentions([]);
      }
    }, 50),
    [token]
  );

  // Modify handleInputChange to better handle name filtering
  const handleInputChange = (e) => {
    const value = e.target.textContent;
    setInputMessage(value);
    
    if (!value.trim()) {
      e.target.classList.add('empty');
    } else {
      e.target.classList.remove('empty');
    }
    
    const lastAtIndex = value.lastIndexOf('@');
    if (lastAtIndex !== -1) {
      const textAfterAt = value.slice(lastAtIndex + 1);
      // Allow spaces in the search query
      if (!/[.,!?(){}[\]]/.test(textAfterAt)) {
        setIsMentioning(true);
        mentionStartIndex.current = lastAtIndex;
        setMentionQuery(textAfterAt);
        
        const query = textAfterAt.toLowerCase();
        const queryParts = query.split(' ').filter(part => part.length > 0);
        
        const filteredMentions = allMentions.filter(mention => {
          // Split name into parts and check if all query parts match
          const nameParts = mention.name.toLowerCase().split(' ');
          return queryParts.every(queryPart =>
            nameParts.some(namePart => namePart.includes(queryPart))
          ) || (mention.team && mention.team.toLowerCase().includes(query)) ||
             (mention.abbreviation && mention.abbreviation.toLowerCase().includes(query));
        }).slice(0, 5);
        
        setMentions(filteredMentions);
        setMentionIndex(0);
        return;
      }
    }
    
    setIsMentioning(false);
    setMentions([]);
  };

  // Update handleMentionSelect to handle the text replacement better
  const handleMentionSelect = (mention) => {
    if (!inputRef.current) return;

    const text = inputRef.current.textContent;
    const beforeMention = text.slice(0, mentionStartIndex.current);
    const afterMention = text.slice(mentionStartIndex.current + mentionQuery.length + 1);
    
    // Create mention element
    const mentionElement = document.createElement('span');
    mentionElement.className = 'mention-tag';
    mentionElement.contentEditable = 'false';
    mentionElement.dataset.mentionId = mention.id;
    mentionElement.dataset.mentionType = mention.type;
    mentionElement.dataset.value = `@${mention.name}`;
    mentionElement.textContent = `@${mention.name}`;
    
    // Clear the input content and rebuild it
    inputRef.current.innerHTML = '';
    
    // Add the parts in sequence
    if (beforeMention) {
      inputRef.current.appendChild(document.createTextNode(beforeMention));
    }
    inputRef.current.appendChild(mentionElement);
    const spaceNode = document.createTextNode(' ');
    inputRef.current.appendChild(spaceNode);
    if (afterMention) {
      inputRef.current.appendChild(document.createTextNode(afterMention));
    }
    
    // Remove empty class since we now have content
    inputRef.current.classList.remove('empty');
    
    // Update state
    setIsMentioning(false);
    setMentions([]);
    setInputMessage(inputRef.current.textContent);
    
    // Move cursor after space
    const selection = window.getSelection();
    const range = document.createRange();
    range.setStartAfter(spaceNode);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  // Prefill mention from query params when landing on the chat page
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const mentionId = params.get('mentionId');
    const mentionName = params.get('mentionName');
    if (mentionId && mentionName && inputRef.current) {
      handleMentionSelect({ id: mentionId, name: mentionName, type: 'player' });
      navigate(location.pathname, { replace: true });
    }
  }, []);

  // Update handleKeyDown to properly handle backspace
  const handleKeyDown = (e) => {
    if (e.key === 'Backspace') {
      const selection = window.getSelection();
      if (!selection.rangeCount) return;
      
      const range = selection.getRangeAt(0);
      const startContainer = range.startContainer;
      const startOffset = range.startOffset;

      // Check if we're right before a mention tag
      if (startContainer.nodeType === Node.TEXT_NODE && startOffset === 0) {
        const prevNode = startContainer.previousSibling;
        if (prevNode?.classList?.contains('mention-tag')) {
          e.preventDefault();
          prevNode.remove();
          setInputMessage(inputRef.current.textContent);
          return;
        }
      }

      // Check if we're inside or at the end of a mention tag
      let mentionElement = null;
      let currentNode = startContainer;
      while (currentNode && !mentionElement) {
        if (currentNode.classList?.contains('mention-tag')) {
          mentionElement = currentNode;
          break;
        }
        currentNode = currentNode.parentNode;
      }
      
      if (mentionElement) {
        e.preventDefault();
        mentionElement.remove();
        setInputMessage(inputRef.current.textContent);
        return;
      }
    }
    
    // Handle arrow keys to prevent cursor movement within mentions
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const selection = window.getSelection();
      if (!selection.rangeCount) return;
      
      const range = selection.getRangeAt(0);
      const node = range.startContainer;
      
      // Check if we're inside or adjacent to a mention
      let mentionElement = null;
      let currentNode = node;
      while (currentNode && !mentionElement) {
        if (currentNode.classList?.contains('mention-tag') || 
            currentNode.classList?.contains('mention-wrapper')) {
          mentionElement = currentNode;
          break;
        }
        currentNode = currentNode.parentNode;
      }
      
      if (mentionElement) {
        e.preventDefault();
        const newRange = document.createRange();
        if (e.key === 'ArrowLeft') {
          newRange.setStartBefore(mentionElement.closest('.mention-wrapper'));
        } else {
          newRange.setStartAfter(mentionElement.closest('.mention-wrapper'));
        }
        newRange.collapse(true);
        selection.removeAllRanges();
        selection.addRange(newRange);
        return;
      }
    }
    
    // Rest of your existing handleKeyDown logic...
    if (isMentioning && mentions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((prev) => (prev + 1) % mentions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((prev) => (prev - 1 + mentions.length) % mentions.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        handleMentionSelect(mentions[mentionIndex]);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setIsMentioning(false);
        setMentions([]);
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      // Only prevent default and handle submission if there's actual content
      if (inputMessage.trim()) {
        e.preventDefault(); // Prevent default to avoid newline in contentEditable
        if (conversationId) {
          // If we're in an existing conversation, submit the message
          handleSubmit(e);
        } else {
          // If we're starting a new chat
          handleNewChat();
        }
      } else {
        // Prevent the enter key from creating a new line when empty
        e.preventDefault();
      }
    }
  };

  const handleRetry = async (userMessageId, assistantMessageId) => {
    try {
      // Start timer for timeout
      const startTime = Date.now();

      // Find the message pair
      const userMessage = currentMessages.find(m => m.id === userMessageId);
      const assistantMessage = currentMessages.find(m => m.id === assistantMessageId);
      
      if (!userMessage || !assistantMessage) {
        console.error('Could not find message pair to retry');
        return;
      }

      setIsStreaming(true);
      setSendingMessages(prev => ({ ...prev, [conversationId]: true }));

      // Find the index of the message pair
      const messageIndex = currentMessages.findIndex(m => m.id === userMessageId);

      // Remove later messages from database and UI
      const deleteResp = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages/after/${assistantMessageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!deleteResp.ok) {
        console.error('Failed to remove old messages');
      }

      setCurrentMessages(prev => prev.slice(0, messageIndex + 1));

      // Start the retry task
      const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/retry`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to retry message');
      }

      const { task_id } = await response.json();
      
      // Store task info in localStorage
      localStorage.setItem(`task_${conversationId}`, JSON.stringify({
        taskId: task_id,
        timestamp: Date.now(),
        userMessage: userMessage.content,
        isRetry: true,
        originalAssistantId: assistantMessageId,
        conversationId: parseInt(conversationId) // Add this
      }));
      setActiveTaskId(task_id);

      // Poll for task status
      while (true) {
        // Check if we've exceeded the timeout
        if (Date.now() - startTime > TASK_TIMEOUT_MS) {
          throw new Error('Request timed out. Please try again.');
        }

        const statusResponse = await fetch(`${API_BASE_URL}/api/tasks/${task_id}`);
        const taskStatus = await statusResponse.json();
        
        if (taskStatus.status === 'not_found') {
          throw new Error('Task not found');
        }
        
        // Update current step
        if (taskStatus.step) {
          setCurrentStep(taskStatus.step);
        }
        
        if (taskStatus.status === 'complete') {
          // Update messages and title
          setCurrentMessages(prev => {
            // Keep the user message and add the new assistant message
            const filtered = prev.filter(msg => 
                msg.id !== assistantMessageId && 
                (!msg.is_temporary || msg.role === 'user')
            );
            return [...filtered, taskStatus.assistant_message];
          });
          
          if (taskStatus.title) {
            setConversations(prev => 
              prev.map(conv => 
                conv.id === parseInt(conversationId)
                  ? { ...conv, title: taskStatus.title }
                  : conv
              )
            );
          }
          break;
        }

        if (taskStatus.status === 'clarification_needed') {
          const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (response.ok) {
            const data = await response.json();
            setCurrentMessages(deduplicateMessages(data));
          }
          setIsStreaming(false);
          setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
          localStorage.removeItem(`task_${conversationId}`);
          setActiveTaskId(null);
          break;
        }

        if (taskStatus.status === 'error') {
          // Update messages with the error message from taskStatus
          setCurrentMessages(prev => {
            const filtered = prev.filter(msg => 
              msg.id !== assistantMessageId && 
              (!msg.is_temporary || msg.role === 'user')
            );
            if (taskStatus.assistant_message) {
              return [...filtered, taskStatus.assistant_message];
            }
            // Fallback error message if no assistant_message in taskStatus
            return [...filtered, {
              id: `error-${Date.now()}`,
              role: 'assistant',
              content: taskStatus.error || 'An error occurred while processing your request.',
              created_at: new Date().toISOString(),
              is_error: true,
              error_message: taskStatus.error
            }];
          });
          throw new Error(taskStatus.error);
        }
        
        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

    } catch (error) {
      console.error('Error retrying message:', error);
      // Only add error message if we don't already have an assistant message
      setCurrentMessages(prev => {
        const hasAssistantMessage = prev.some(msg => 
          msg.role === 'assistant' && !msg.is_temporary
        );
        if (!hasAssistantMessage) {
          return [...prev, {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `Error: ${error.message}`,
            created_at: new Date().toISOString(),
            is_error: true,
            error_message: error.message
          }];
        }
        return prev;
      });
    } finally {
      setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
      setIsStreaming(false);
      setCurrentStep('');
      localStorage.removeItem(`task_${conversationId}`);
      setActiveTaskId(null);
    }
  };

  // Add this new useEffect near your other useEffects
  useEffect(() => {
    const fetchAllMentions = async () => {
      try {
        setIsLoadingMentions(true);
        const response = await fetch(`${API_BASE_URL}/api/mentions`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (response.ok) {
          const data = await response.json();
          setAllMentions(data);
        }
      } catch (error) {
        console.error('Error fetching mentions:', error);
      } finally {
        setIsLoadingMentions(false);
      }
    };

    fetchAllMentions();
  }, [token]);

  // Add this log inside the component to check message structure when they arrive
  useEffect(() => {
    console.log("Current Messages Updated:", currentMessages);
  }, [currentMessages]);

  // Add this useEffect to handle step completion
  useEffect(() => {
    if (currentStep && !completedSteps.includes(currentStep)) {
      setCompletedSteps(prev => [...prev, currentStep]);
    }
  }, [currentStep]);

  // Add this useEffect to handle streaming state
  useEffect(() => {
    if (isStreaming) {
      setShowSteps(true);
    } else {
      // Only reset steps when streaming stops, but keep the messages
      setCompletedSteps([]);
      setShowSteps(false);
      setCurrentStep('');
    }
  }, [isStreaming]);

  // Modify the task polling useEffect
  useEffect(() => {
    // Clear UI state when conversation changes
    setIsStreaming(false);
    setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
    setActiveTaskId(null);
    setCompletedSteps([]);
    setShowSteps(false);
    setCurrentStep('');

    let isCurrentConversation = true; // Add this flag

    // Check if there's an active task for this conversation
    const storedTask = localStorage.getItem(`task_${conversationId}`);
    if (storedTask) {
      try {
        const taskData = JSON.parse(storedTask);
        if (taskData.conversationId !== parseInt(conversationId)) {
          return;
        }

        const taskId = taskData.taskId;
        const userMessage = taskData.userMessage;
        const startTime = taskData.timestamp;
        
        if (isCurrentConversation) {
          setActiveTaskId(taskId);
          setIsStreaming(true);
          setSendingMessages(prev => ({ ...prev, [conversationId]: true }));
        }

        // First fetch existing messages
        const fetchMessages = async () => {
          try {
            const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
              headers: {
                'Authorization': `Bearer ${token}`
              }
            });
            if (response.ok && isCurrentConversation) {
              const messages = await response.json();
              const processed = messages.map(m => ({
                ...m,
                is_error: m.is_error || (m.error_message && m.error_message.length > 0),
                error_message: m.error_message || null
              }));
              let result = processed;
              if (taskData.isRetry) {
                result = result.filter(msg => msg.id !== taskData.originalAssistantId);
              } else {
                if (userMessage && !result.some(m => m.content === userMessage || m.is_temporary)) {
                  result.push({
                    role: 'user',
                    content: userMessage,
                    id: `temp-${taskId}`,
                    created_at: new Date().toISOString(),
                    is_temporary: true
                  });
                }
              }
              setCurrentMessages(deduplicateMessages(result));
            }
          } catch (error) {
            console.error('Error fetching messages:', error);
          }
        };

        fetchMessages();

        // Start polling for the task
        let pollTimeout;
        const pollTask = async () => {
          try {
            if (!isCurrentConversation) return;

            if (Date.now() - startTime > TASK_TIMEOUT_MS) {
              throw new Error('Task timed out after 50 seconds');
            }

            const statusResponse = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`);
            const taskStatus = await statusResponse.json();

            if (!isCurrentConversation) return;

            if (taskStatus.status === 'not_found') {
              throw new Error('Task not found');
            }

            if (taskStatus.step) {
              setCurrentStep(taskStatus.step);
              const allSteps = ['Analyzing your question...', 'Fetching data...', 'Generating a response...'];
              const currentIndex = allSteps.indexOf(taskStatus.step);
              const stepsToComplete = allSteps.slice(0, currentIndex);
              setCompletedSteps(stepsToComplete);
              setShowSteps(true);
            }

            if (taskStatus.status === 'complete') {
                setCurrentMessages(prev => {
                    // Keep all non-temporary messages and the temporary user message
                    const filtered = prev.filter(msg => 
                        !msg.is_temporary || 
                        (msg.is_temporary && msg.role === 'user')
                    );
                    return [...filtered, taskStatus.assistant_message];
                });

                if (taskStatus.title) {
                    setConversations(prev => 
                        prev.map(conv => 
                            conv.id === parseInt(conversationId)
                                ? { ...conv, title: taskStatus.title }
                                : conv
                        )
                    );
                }

                localStorage.removeItem(`task_${conversationId}`);
                setIsStreaming(false);
                setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
                setActiveTaskId(null);
                setCompletedSteps([]);
                setShowSteps(false);
                setCurrentStep('');
            } else if (taskStatus.status === 'error') {
                // For error states, keep the user message but update the assistant message
                setCurrentMessages(prev => {
                    // Keep all messages except temporary assistant messages
                    const filtered = prev.filter(msg => 
                        !msg.is_temporary || 
                        (msg.is_temporary && msg.role === 'user')
                    );
                    // Add the error message if it exists
                    if (taskStatus.assistant_message) {
                        return [...filtered, taskStatus.assistant_message];
                    }
                    return filtered;
                });
                throw new Error(taskStatus.error);
            } else if (taskStatus.status === 'clarification_needed') {
              // Fetch latest messages and update the chat
              const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
                headers: { 'Authorization': `Bearer ${token}` }
              });
              if (response.ok) {
                const data = await response.json();
                setCurrentMessages(deduplicateMessages(data));
              }
              setIsStreaming(false);
              setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
              setActiveTaskId(null);
              setCompletedSteps([]);
              setShowSteps(false);
              setCurrentStep('');
              localStorage.removeItem(`task_${conversationId}`);
              return;
            } else {
                pollTimeout = setTimeout(pollTask, 1000);
            }
          } catch (error) {
            if (isCurrentConversation) {
              console.error('Error polling task:', error);
              localStorage.removeItem(`task_${conversationId}`);
              setIsStreaming(false);
              setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
              setActiveTaskId(null);
              setCompletedSteps([]);
              setShowSteps(false);

              // Only update the error message if we don't already have an assistant message
              setCurrentMessages(prev => {
                  const hasAssistantMessage = prev.some(msg => 
                      msg.role === 'assistant' && !msg.is_temporary
                  );
                  if (!hasAssistantMessage) {
                      const filtered = prev.filter(msg => 
                          !msg.is_temporary || 
                          (msg.is_temporary && msg.role === 'user')
                      );
                      // Extract just the error message without the status code
                      const errorMessage = error.message.includes(': ') 
                          ? error.message.split(': ').slice(1).join(': ')
                          : error.message;
                      return [...filtered, {
                          role: 'assistant',
                          content: errorMessage,
                          id: 'error-' + Date.now(),
                          created_at: new Date().toISOString(),
                          is_error: true,
                          error_message: errorMessage
                      }];
                  }
                  return prev;
              });
            }
          }
        };

        pollTask();

        // Cleanup function
        return () => {
          isCurrentConversation = false;
          clearTimeout(pollTimeout);
        };
      } catch (e) {
        console.error('Error parsing stored task:', e);
        localStorage.removeItem(`task_${conversationId}`);
      }
    }
  }, [conversationId, token]);

  // Add this useEffect to clean up old tasks
  useEffect(() => {
    // Clean up tasks older than 5 minutes
    const cleanupTasks = () => {
      const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key.startsWith('task_')) {
          try {
            const taskData = JSON.parse(localStorage.getItem(key));
            if (taskData.timestamp < fiveMinutesAgo) {
              localStorage.removeItem(key);
            }
          } catch (e) {
            // Invalid JSON, remove the item
            localStorage.removeItem(key);
          }
        }
      }
    };

    cleanupTasks();
    const interval = setInterval(cleanupTasks, 60000); // Clean up every minute
    
    return () => clearInterval(interval);
  }, []);

  // Update the messages persistence effect
  useEffect(() => {
    if (currentMessages.length > 0) {
        // Store limited number of messages in localStorage with their error state
        const deduped = deduplicateMessages(currentMessages);
        const limited = limitMessages(deduped);
        safeSetItem(
            `messages_${conversationId}`,
            JSON.stringify(limited)
        );
    }
  }, [currentMessages, conversationId]);

  // Update the messages loading effect
  useEffect(() => {
    try {
        const savedMessages = localStorage.getItem(`messages_${conversationId}`);
        if (savedMessages) {
            const parsed = JSON.parse(savedMessages);
            setCurrentMessages(deduplicateMessages(parsed));
        }
    } catch (err) {
        console.warn('Error loading messages from localStorage:', err);
        // If there's an error loading messages, clear this conversation's cache
        localStorage.removeItem(`messages_${conversationId}`);
    }
  }, [conversationId]);

  const handleEditMessage = (messageId, content) => {
    if (editingMessageId === messageId) {
      // If clicking edit button again, cancel edit
      setEditingMessageId(null);
      setEditingContent('');
    } else {
      setEditingMessageId(messageId);
      setEditingContent(content);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    console.log('handleEditSubmit called');
    console.log('editingMessageId:', editingMessageId);
    console.log('editingContent:', editingContent);

    if (!editingMessageId || !editingContent.trim()) {
      console.log('No message ID or content, returning');
      return;
    }

    try {
      console.log('Sending update request to:', `${API_BASE_URL}/api/messages/${editingMessageId}`);
      // Update the message in the database
      const response = await fetch(`${API_BASE_URL}/api/messages/${editingMessageId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ content: editingContent })
      });

      console.log('Update response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Update failed:', errorText);
        throw new Error('Failed to update message');
      }

      console.log('Sending delete request for subsequent messages');
      // Delete all messages after this one
      const deleteResponse = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages/after/${editingMessageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      console.log('Delete response status:', deleteResponse.status);
      if (!deleteResponse.ok) {
        const errorText = await deleteResponse.text();
        console.error('Delete failed:', errorText);
        throw new Error('Failed to delete subsequent messages');
      }

      console.log('Clearing messages and edit state');
      // Clear current messages to trigger a refresh
      setCurrentMessages([]);
      setEditingMessageId(null);
      setEditingContent('');
    } catch (error) {
      console.error('Error in handleEditSubmit:', error);
      // You might want to show an error message to the user here
    }
  };

  const handleCopyMessage = (content) => {
    navigator.clipboard.writeText(content);
  };

  const handleStopResponse = async () => {
    setIsStoppingResponse(true);
    try {
      // Cancel the current task
      const taskData = JSON.parse(localStorage.getItem(`task_${conversationId}`));
      if (taskData?.taskId) {
        await fetch(`${API_BASE_URL}/api/tasks/${taskData.taskId}/cancel`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      }
    } catch (error) {
      console.error('Error stopping response:', error);
    } finally {
      setIsStoppingResponse(false);
      setIsStreaming(false);
      setSendingMessages(prev => ({ ...prev, [conversationId]: false }));
      localStorage.removeItem(`task_${conversationId}`);
      setActiveTaskId(null);
    }
  };

  // Add click outside handler for edit mode
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (editingMessageId && editInputRef.current && !editInputRef.current.contains(event.target)) {
        setEditingMessageId(null);
        setEditingContent('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [editingMessageId]);

  const parseImagesSection = (content) => {
    const imagesMatch = content.match(/##Images: ({.*?})/);
    if (!imagesMatch) return null;
    
    try {
      const imagesDict = JSON.parse(imagesMatch[1].replace(/'/g, '"'));
      return imagesDict;
    } catch (e) {
      console.error('Error parsing images section:', e);
      return null;
    }
  };

  const removeImagesSection = (content) => {
    return content.replace(/##Images: {.*?}\n?/s, '');
  };

  const renderImages = (imagesDict) => {
    if (!imagesDict) return null;

    return (
      <div className="flex items-center space-x-20 mb-8">
        {Object.entries(imagesDict).map(([type, ids]) => {
          if (!Array.isArray(ids)) return null;
          
          return ids.map((id) => {
            const imageUrl = `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/${type.toLowerCase()}s/${id}.png`;
            const linkUrl = type === 'Sportsbook' ? null : `${process.env.REACT_APP_FRONTEND_URL}/mlb/${type.toLowerCase()}s/${id}`;
            
            return (
              <div key={`${type}-${id}`} className="flex flex-col items-center">
                <img
                  src={imageUrl}
                  alt={`${type} ${id}`}
                  className="w-20 h-20 rounded-full object-cover shadow-md"
                />
                {linkUrl && (
                  <a href={linkUrl}>
                    <span className="text-white font-bold text-md hover:text-red-600">{type} {id}</span>
                  </a>
                )}
              </div>
            );
          });
        })}
      </div>
    );
  };

  return (
    <div 
      className="flex h-screen bg-dark-900 overflow-hidden"
      style={{ userSelect: isResizing ? 'none' : 'auto' }}
    >
      {/* Sidebar */}
      <div 
        className={`${isSidebarOpen ? '' : 'w-0'} transition-all duration-300 bg-dark-900 border-r border-white/5 flex flex-col overflow-hidden relative`}
        style={{ 
          width: isSidebarOpen ? `${sidebarWidth}px` : '0',
          minWidth: isSidebarOpen ? '150px' : '0',
          maxWidth: '600px',
          height: 'calc(100vh - 64px)', // Subtract navbar height
          position: 'fixed',
          left: 0,
          top: '64px', // Add top offset for navbar
          zIndex: 40
        }}
      >
        {/* Fixed header */}
        <div className="p-3 border-b border-white/5 bg-dark-900" 
          style={{ 
            width: isSidebarOpen ? `${sidebarWidth}px` : '0',
            opacity: isSidebarOpen ? '1' : '0',
            visibility: isSidebarOpen ? 'visible' : 'hidden',
            transition: 'width 0.3s, opacity 0.3s, visibility 0.3s'
          }}
        >
          <div className="flex items-center justify-between mb-2"> {/* Reduced mb-6 to mb-2 */}
            {/* Sidebar close button */}
            <button
              onClick={handleSidebarClose}
              className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-dark-700 transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 9V5.25A2.25 2.25 0 0 1 10.5 3h6a2.25 2.25 0 0 1 2.25 2.25v13.5A2.25 2.25 0 0 1 16.5 21h-6a2.25 2.25 0 0 1-2.25-2.25V15m-3 0-3-3m0 0 3-3m-3 3H15" />
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSearchToggle}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-dark-700 transition-colors" /* Reduced p-2 to p-1.5 */
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </button>
              <button
                onClick={handleNewChatClick}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-dark-700 transition-colors" /* Reduced p-2 to p-1.5 */
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </div>
          </div>
          {isSearching && (
            <div className="px-0">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversations..."
                className="w-full px-6 py-3.5 bg-dark-700 rounded-lg text-white placeholder-gray-500 border border-white/5 focus:ring-2 focus:ring-red-500/20 focus:border-red-500/20 focus:outline-none transition-colors"
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {Object.entries(groupedConversations)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([league, convs]) => (
              <div key={league}>
                <div className="px-4 py-2 text-xs font-semibold text-gray-400 bg-dark-700/50">
                  {league}
                </div>
                {convs
                  .filter(conv => 
                    !searchQuery || 
                    conv.title?.toLowerCase().includes(searchQuery.toLowerCase())
                  )
                  .map((conversation, index) => (
                    <div
                      key={conversation.id}
                      onClick={() => navigate(`/chat/${conversation.id}`)}
                      className={`group px-4 py-3 hover:bg-dark-700 cursor-pointer ${
                        conversation.id === parseInt(conversationId) ? 'bg-dark-700' : ''
                      }`}
                      style={{
                        animation: `fadeIn 0.3s ease-out ${index * 0.05}s both`
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-gray-300 group-hover:text-white min-w-0">
                          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2z" />
                          </svg>
                          {isEditing && conversation.id === editingId ? (
                            <input
                              type="text"
                              value={editedTitle}
                              onChange={(e) => setEditedTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  handleUpdateTitle(conversation.id, editedTitle);
                                } else if (e.key === 'Escape') {
                                  setIsEditing(false);
                                }
                              }}
                              onBlur={() => handleUpdateTitle(conversation.id, editedTitle)}
                              className="bg-dark-800 text-white px-2 py-1 rounded-md w-full"
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <span 
                              className="truncate"
                              style={{ maxWidth: `${sidebarWidth - 100}px` }}  // Subtract space for icons
                              onDoubleClick={(e) => {
                                e.stopPropagation();
                                if (isEditing && editingId && editingId !== conversation.id) {
                                  handleUpdateTitle(editingId, editedTitle, false);
                                }
                                setEditingId(conversation.id);
                                setEditedTitle(conversation.title || 'New Chat');
                                setIsEditing(true);
                              }}
                            >
                              {conversation.title || 'New Chat'}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (isEditing && editingId && editingId !== conversation.id) {
                                handleUpdateTitle(editingId, editedTitle, false);
                              }
                              setEditingId(conversation.id);
                              setEditedTitle(conversation.title || 'New Chat');
                              setIsEditing(true);
                            }}
                            className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-white transition-opacity p-1"
                            title="Rename chat"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteConversation(conversation.id);
                            }}
                            className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-white transition-opacity p-1"
                            title="Delete chat"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            ))}
        </div>

        {/* Resize handle */}
        <div
          className="absolute top-0 right-0 bottom-0 w-[2px] cursor-ew-resize hover:bg-white/20 transition-colors"
          onMouseDown={(e) => {
            e.preventDefault();
            setIsResizing(true);
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
          }}
        />
      </div>

      {/* Add a spacer div to push main content over */}
      <div style={{ 
        width: isSidebarOpen ? `${sidebarWidth}px` : '0px',
        flexShrink: 0,
        transition: 'width 0.3s',
        marginTop: '64px' // Add top margin to match sidebar offset
      }} />

      {/* Main content area - add overflow-y-auto here */}
      <div className={`flex-1 overflow-y-auto ${!isSidebarOpen ? 'pl-16' : ''}`}>
        {/* Sidebar open button (show only when sidebar is closed) */}
        {!isSidebarOpen && (
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="fixed top-20 left-2 z-50 p-2 text-gray-400 hover:text-white rounded-lg hover:bg-dark-700 transition-colors shadow-lg bg-dark-800"
            aria-label="Open sidebar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-6 h-6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
            </svg>
          </button>
        )}

        {/* Welcome Screen or Chat */}
        {!conversationId ? (
          <div className="flex-1 flex flex-col bg-dark-900">
            <UpcomingGamesTicker onGameClick={handleGameSelect} selectedGameId={selectedGameId} />
            <div className="flex-1 flex items-center justify-center">
              <div className="max-w-2xl w-full px-8 space-y-8 mt-10">
                <div className="text-center space-y-4"
                  style={{ 
                    animation: 'fadeInScale 0.6s ease-out',
                    marginTop: 0
                  }}>
                  <img 
                    src={blitzLogo} 
                    alt="Blitz" 
                    className="h-20 mx-auto hover:scale-105 transition-transform duration-300"
                    style={{ 
                      animation: 'pulseGlow 3s ease-in-out infinite'
                    }}
                  />
                  <p className="text-white mb-4 text-lg">
                    Ask me anything about baseball statistics and analytics
                  </p>
                </div>

                {/* Wrapper for Input and Mode Buttons on New Chat Page */}
                <div className="relative mb-8" style={{ animation: 'slideInFromBottom 0.6s ease-out 0.2s both' }}>
                  {/* Input Area for New Chat */}
                  <div className="relative flex items-center gap-3">
                    {/* ... existing inputRef div and submit button ... */}
                    <div className="relative flex-1">
                      <div
                        ref={inputRef}
                        contentEditable
                        className="empty w-full min-h-[50px] px-6 py-3.5 rounded-xl bg-dark-800/50 text-white placeholder-gray-500 border border-white/10 hover:border-white/30 focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:outline-none transition-colors duration-200 backdrop-blur-sm overflow-y-auto"
                        placeholder="Send a message..."
                        onInput={(e) => {
                          handleInputChange(e);
                          if (!e.target.textContent.trim()) {
                            e.target.classList.add('empty');
                          } else {
                            e.target.classList.remove('empty');
                          }
                          e.target.style.height = 'auto';
                          const newHeight = Math.min(e.target.scrollHeight, 300); // Increased max height
                          e.target.style.height = `${newHeight}px`;
                        }}
                        onPaste={(e) => {
                          setTimeout(() => {
                            const el = e.target;
                            el.style.height = 'auto';
                            const newHeight = Math.min(el.scrollHeight, 300);
                            el.style.height = `${newHeight}px`;
                          }, 0);
                        }}
                        onKeyDown={handleKeyDown}
                        style={{
                          minHeight: '50px',
                          maxHeight: '300px',
                          overflowY: 'auto',
                          wordWrap: 'break-word',
                          whiteSpace: 'pre-wrap',
                          overflowWrap: 'break-word',
                          width: '100%',
                          display: 'block',
                          textOverflow: 'ellipsis',
                          fontSize: '16px'
                        }}
                      />
                      {isMentioning && (
                        <MentionsList
                          mentions={mentions}
                          selectedIndex={mentionIndex}
                          onSelect={handleMentionSelect}
                        />
                      )}
                    </div>

                    {/* Submit Button */}
                    {(inputRef.current?.textContent.trim() || inputMessage.trim()) && ( // Check ref content too
                      <button
                        // Use handleNewChat directly here since we are on the new chat page
                        onClick={handleNewChat} 
                        type="button" // Change type to button to prevent form submission if wrapped
                        disabled={isNewChatLoading || sendingMessages[conversationId]} // Use isNewChatLoading here
                        className="w-10 h-10 flex items-center justify-center rounded-full bg-white text-dark-900 hover:bg-gray-200 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isNewChatLoading ? ( // Use isNewChatLoading here
                          <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Example Questions Section */}
                <div style={{ 
                  animation: 'slideInFromBottom 0.6s ease-out 0.4s both'
                }}>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-medium text-gray-400 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      Try these example questions:
                    </h2>
                    <button
                      onClick={handleShuffleQuestions}
                      className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-dark-700 transition-colors relative group"
                      data-tooltip="Shuffle"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      <span className="absolute -top-8 left-1/2 transform -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        Shuffle
                      </span>
                    </button>
                  </div>
                  <div className={`grid grid-cols-1 gap-3 transition-opacity duration-300 ${isTransitioningQuestions ? 'opacity-0' : 'opacity-100'}`}>
                    {displayedQuestions.map((question, index) => (
                      <button
                        key={index}
                        onClick={() => {
                          setInputMessage(question);
                          if (inputRef.current) {
                            inputRef.current.textContent = question;
                            inputRef.current.classList.remove('empty');
                          }
                        }}
                        className="text-left p-4 rounded-xl bg-dark-800/50 hover:bg-dark-700/50 text-gray-300 hover:text-white transition-all duration-300 border border-white/5 hover:border-white/20 hover:translate-x-1 backdrop-blur-sm"
                        style={{ 
                          animation: `slideInFromBottom 0.6s ease-out ${0.6 + index * 0.1}s both`
                        }}
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="min-h-full pb-36"> {/* Reduced from pb-48 to pb-36 */}
            {/* Messages container */}
            <div 
              ref={chatContainerRef}
              className="p-4 space-y-4" /* Reduced space-y-6 to space-y-4 for more compact messages */
            >
              {currentMessages.filter(message => message && message.role).map((message, index) => {
                const isAssistant = message.role === "assistant";
                const isHelpful = helpfulStates[index]?.isHelpful;
                const isUnhelpful = unhelpfulStates[index]?.isUnhelpful;

                return (
                  <div key={index} className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}>
                    {isAssistant && (
                      <div className="w-8 h-8 mr-4 flex-shrink-0">
                        <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center">
                          <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                          </svg>
                        </div>
                      </div>
                    )}
                    
                    <div className={`flex flex-col ${isAssistant ? "items-start" : "items-end"} max-w-3xl`}>
                      <div 
                        className={`${isAssistant ? "bg-dark-800" : "bg-dark-700"} p-4 rounded-2xl relative`}
                        ref={isAssistant ? (el) => messageRefs.current[index] = el : null}
                      >
                        {message.role === 'assistant' ? (
                          <>
                            {/* Show error notification if there's a retry error for this message */}
                            {retryErrors[message.id] && (
                              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-3 text-sm text-red-400">
                                <div className="flex items-center gap-2">
                                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                  </svg>
                                  <span>{retryErrors[message.id]}</span>
                                </div>
                              </div>
                            )}
                            
                            {/* Error message display - check both is_error and error_message */}
                            {(message.is_error || message.error_message) ? (
                              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-400">
                                <div className="flex items-center gap-2">
                                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                  </svg>
                                  <span>{message.error_message || message.content}</span>
                                </div>
                              </div>
                            ) : (
                              // Regular message content
                              <>
                                {message.response_mode === 'text' ? (
                                  <div className="prose prose-sm prose-invert max-w-none text-white [&_a]:text-red-600 [&_a]:no-underline [&_a:hover]:text-red-800">
                                    {renderImages(parseImagesSection(message.content))}
                                    <ReactMarkdown 
                                      remarkPlugins={[remarkGfm]}
                                      rehypePlugins={[rehypeRaw]}
                                      components={{
                                        hr: ({node, ...props}) => <hr className="my-4" {...props} />, 
                                        h1: ({node, ...props}) => <h1 className="mt-4" {...props} />, 
                                        h2: ({node, ...props}) => <h2 className="mt-4" {...props} />, 
                                        h3: ({node, ...props}) => <h3 className="mt-4" {...props} />, 
                                        h4: ({node, ...props}) => <h4 className="mt-4" {...props} />, 
                                        h5: ({node, ...props}) => <h5 className="mt-4" {...props} />, 
                                        h6: ({node, ...props}) => <h6 className="mt-4" {...props} />, 
                                        font: ({node, color, ...props}) => {
                                          // Map color names to Tailwind classes
                                          const colorMap = {
                                            'white': 'text-white',
                                            'red': 'text-red-400',
                                            'green': 'text-green-400'
                                          };
                                          return <span className={colorMap[color] || 'text-white'} {...props} />;
                                        }
                                      }}
                                    >
                                      {removeFontBackticks(removeImagesSection(message.content))}
                                    </ReactMarkdown>
                                  </div>
                                ) : (
                                  <div className="prose prose-sm prose-invert max-w-none text-white [&_a]:text-red-600 [&_a]:no-underline [&_a:hover]:text-red-800">
                                    <JsxParser
                                      components={{ ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, BarChart, Bar, PieChart, Pie, ScatterChart, Scatter, CartesianGrid, Legend }}
                                      jsx={message.content}
                                      onError={(error) => console.error('JSXParser Error:', error)}
                                    />
                                  </div>
                                )}
                              </>
                            )}
                          </>
                        ) : (
                          <>
                            {editingMessageId === message.id ? (
                              <div ref={editInputRef} className="w-full max-w-3xl">
                                <form onSubmit={handleEditSubmit} className="flex items-end gap-2">
                                  <textarea
                                    value={editingContent}
                                    onChange={(e) => setEditingContent(e.target.value)}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleEditSubmit(e);
                                      }
                                    }}
                                    className="flex-1 w-full min-h-[100px] bg-dark-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                                    autoFocus
                                  />
                                  <button
                                    type="submit"
                                    className="w-10 h-10 flex items-center justify-center rounded-full bg-white text-dark-900 hover:bg-gray-200 transition-colors shadow-md"
                                  >
                                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                    </svg>
                                  </button>
                                </form>
                              </div>
                            ) : (
                              <p className="text-white m-0 whitespace-pre-wrap cursor-text">
                                {message.content}
                              </p>
                            )}
                          </>
                        )}
                      </div>

                      {/* Timestamp and buttons container */}
                      <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                        {/* User message action buttons - on the left */}
                        {message.role === 'user' && !isStreaming && !sendingMessages[conversationId] && (
                          <>
                            {/* <button
                              onClick={() => handleEditMessage(message.id, message.content)}
                              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
                              title="Edit message"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                            <button
                              onClick={() => handleCopyMessage(message.content)}
                              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors"
                              title="Copy message"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                              </svg>
                            </button> */}
                          </>
                        )}

                        {/* Timestamp in the middle */}
                        <span className="text-xs text-gray-500">
                          {message.created_at ? new Date(message.created_at).toLocaleTimeString([], { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          }) : ''}
                        </span>

                        {/* Assistant message action buttons - on the right */}
                          {isAssistant && (
                          <>
                            {message.is_error ? (
                              <button
                                onClick={() => handleRetry(currentMessages[index - 1]?.id, message.id)}
                                disabled={sendingMessages[conversationId]}
                                className="p-1 text-gray-400 hover:text-gray-200 disabled:opacity-50"
                              >
                                <svg
                                  className="w-4 h-4"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                  strokeWidth={2}
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                  />
                                </svg>
                              </button>
                            ) : (
                              <>
                                <button
                                  onClick={() => handleToggleHelpful(index)}
                                  className={`p-1 rounded transition-colors ${isHelpful ? 'text-green-400' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"
                                    />
                                  </svg>
                                </button>

                                <button
                                  onClick={() => handleToggleUnhelpful(index)}
                                  className={`p-1 rounded transition-colors ${isUnhelpful ? 'text-red-400' : 'text-gray-400 hover:text-gray-200'}`}
                                >
                                  <svg
                                    className="w-4 h-4 transform rotate-180"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"/>
                                  </svg>
                                </button>

                                <button
                                  onClick={() => handleRetry(currentMessages[index - 1]?.id, message.id)}
                                  disabled={sendingMessages[conversationId]}
                                  className="p-1 text-gray-400 hover:text-gray-200 disabled:opacity-50"
                                >
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                                    />
                                  </svg>
                                </button>

                                <button
                                  onClick={(e) => handleShare(messageRefs.current[index])}
                                  className="p-1 text-gray-400 hover:text-gray-200"
                                >
                                  <svg
                                    className="w-4 h-4"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z"
                                    />
                                  </svg>
                                </button>
                              </>
                            )}
                          </>
                        )}
                      </div>
                    </div>

                    {message.role === 'user' && (
                      <div className="w-8 h-8 ml-4 flex-shrink-0">
                        <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center">
                          <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Typing indicator */}
              {showSteps && (
                <div className="flex justify-start">
                  <div className="w-8 h-8 mr-4 flex-shrink-0">
                    <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center">
                      <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                  </div>
                  <div className="bg-dark-800/50 rounded-2xl rounded-tl-none p-4 space-y-2 pulse-animation">
                    {completedSteps.map((step, index) => (
                      <div key={index} className="flex items-center gap-2 text-gray-300 text-base font-medium">
                        {step.includes("Analyzing") && (
                          <svg className="w-5 h-5 text-indigo-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                          </svg>
                        )}
                        {step.includes("Fetching") && (
                          <svg className="w-5 h-5 text-emerald-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                          </svg>
                        )}
                        {step.includes("Generating") && (
                          <svg className="w-5 h-5 text-amber-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        )}
                        <span className="flex-1">{step}</span>
                        {step !== currentStep && (
                          <svg className="w-5 h-5 text-emerald-500 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                          </svg>
                        )}
                      </div>
                    ))}
                    {currentStep && !completedSteps.includes(currentStep) && (
                      <div className="flex items-center gap-2 pulse-animation">
                        {currentStep.includes("Analyzing") && (
                          <svg className="w-5 h-5 text-indigo-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
                          </svg>
                        )}
                        {currentStep.includes("Fetching") && (
                          <svg className="w-5 h-5 text-emerald-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                          </svg>
                        )}
                        {currentStep.includes("Generating") && (
                          <svg className="w-5 h-5 text-amber-400 pulse-animation" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        )}
                        <span className="text-gray-300 text-base font-medium pulse-animation">{currentStep}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>
        )}

        {/* Chat Input Area - keep fixed positioning */}
        {conversationId && (
          <div className="fixed bottom-0 right-0 border-t border-white/5 p-4 bg-dark-900" style={{ 
            left: isSidebarOpen ? `${sidebarWidth}px` : '0px'
          }}>
            {/* Input Form (Existing Chat) */}
            <form onSubmit={handleSubmit} className="relative">
               {/* ... Keep the existing input form here ... */}
               <div className="relative flex items-center gap-3">
                 <div className="relative flex-1">
                   <div
                     ref={inputRef}
                     contentEditable
                     className="empty w-full min-h-[50px] px-6 py-3.5 rounded-xl bg-dark-800/50 text-white placeholder-gray-500 border border-white/10 hover:border-white/30 focus:border-white/30 focus:ring-1 focus:ring-white/30 focus:outline-none transition-colors duration-200 backdrop-blur-sm overflow-y-auto"
                     placeholder="Send a message..."
                     onInput={(e) => {
                       handleInputChange(e);
                       if (!e.target.textContent.trim()) {
                         e.target.classList.add('empty');
                       } else {
                         e.target.classList.remove('empty');
                       }
                       e.target.style.height = 'auto';
                       const newHeight = Math.min(e.target.scrollHeight, 300); // Increased max height
                       e.target.style.height = `${newHeight}px`;
                     }}
                     onPaste={(e) => {
                       setTimeout(() => {
                         const el = e.target;
                         el.style.height = 'auto';
                         const newHeight = Math.min(el.scrollHeight, 300);
                         el.style.height = `${newHeight}px`;
                       }, 0);
                     }}
                     onKeyDown={handleKeyDown}
                     style={{
                       minHeight: '50px',
                       maxHeight: '300px',
                       overflowY: 'auto',
                       wordWrap: 'break-word',
                       whiteSpace: 'pre-wrap',
                       overflowWrap: 'break-word',
                       width: '100%',
                       display: 'block',
                       textOverflow: 'ellipsis',
                       fontSize: '16px'
                     }}
                   />
                   {isMentioning && (
                     <MentionsList
                       mentions={mentions}
                       selectedIndex={mentionIndex}
                       onSelect={handleMentionSelect}
                     />
                   )}
                 </div>

                 {/* Submit Button */}
                 {(inputRef.current?.textContent.trim() || inputMessage.trim()) && ( // Check ref content too
                   <button
                     type="submit"
                     disabled={sendingMessages[conversationId]}
                     className="w-10 h-10 flex items-center justify-center rounded-full bg-white text-dark-900 hover:bg-gray-200 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                   >
                     {sendingMessages[conversationId] ? (
                       <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                     ) : (
                       <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                         <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                       </svg>
                     )}
                   </button>
                 )}
               </div>
            </form>
          </div>
        )}
      </div>
      <ShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        screenshotUrl={screenshotUrl}
        onCopyImage={handleCopyImage}
        onTwitterShare={handleTwitterShare}
      />
    </div>
  );
}

const MentionsList = ({ mentions, selectedIndex, onSelect }) => {
  if (!mentions.length) return null;

  return (
    <div className="absolute bottom-full mb-2 w-full max-h-60 overflow-y-auto bg-dark-800 rounded-lg border border-white/10 shadow-lg divide-y divide-white/5">
      {mentions.map((mention, index) => (
        <button
          key={mention.id}
          className={`w-full px-4 py-3 text-left hover:bg-dark-700 flex items-center gap-3 transition-colors ${
            index === selectedIndex ? 'bg-dark-700' : ''
          }`}
          onClick={() => onSelect(mention)}
        >
          <div className="relative">
            <img 
              src={
                mention.type === 'player'
                  ? `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/players/${mention.id}.png`
                  : mention.type === 'team'
                  ? `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/teams/${mention.id}.png`
                  : defaultPlayerImage
              }
              alt=""
              className="w-8 h-8 rounded-full object-cover border border-white/10"
              onError={(e) => {
                e.target.src = defaultPlayerImage;
              }}
            />
            <span className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-medium ${
              mention.type === 'player' ? 'bg-blue-500' :
              mention.type === 'team' ? 'bg-green-500' : 'bg-purple-500'
            }`}>
              {mention.type[0].toUpperCase()}
            </span>
          </div>
          <div>
            <span className="text-white font-medium">{mention.name}</span>
            {mention.team && (
              <span className="text-gray-400 text-sm ml-2">({mention.team})</span>
            )}
            <div className="text-gray-400 text-xs mt-0.5">
              {mention.type === 'player' ? 'MLB Player' : 
               mention.type === 'team' ? 'MLB Team' : 'Sportsbook'}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
};

const MentionTag = ({ mention, onRemove }) => {
  const getImageUrl = () => {
    switch (mention.type) {
      case 'player':
        return `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/players/${mention.id}.png`;
      case 'team':
        return `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/teams/${mention.id}.png`;
      case 'sportsbook':
        return `https://blitzanalytics-mlb-images.s3.us-west-2.amazonaws.com/sportsbooks/${mention.id}.png`;
      default:
        return defaultPlayerImage;
    }
  };

  const getBgColor = () => {
    switch (mention.type) {
      case 'player':
        return 'bg-blue-500/10 border-blue-500/20';
      case 'team':
        return 'bg-green-500/10 border-green-500/20';
      case 'sportsbook':
        return 'bg-purple-500/10 border-purple-500/20';
      default:
        return 'bg-gray-500/10 border-gray-500/20';
    }
  };

  return (
    <span className={`inline-flex items-center gap-2 px-2 py-1.5 rounded-lg border ${getBgColor()} mr-1.5`}>
      <div className="relative">
        <img 
          src={getImageUrl()}
          alt=""
          className="w-5 h-5 rounded-full border border-white/10"
          onError={(e) => {
            e.target.src = defaultPlayerImage;
          }}
        />
        <span className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full text-[8px] flex items-center justify-center font-medium ${
          mention.type === 'player' ? 'bg-blue-500' :
          mention.type === 'team' ? 'bg-green-500' : 'bg-purple-500'
        }`}>
          {mention.type[0].toUpperCase()}
        </span>
      </div>
      <span className="text-white font-medium">{mention.name}</span>
      <button 
        onClick={onRemove}
        className="text-gray-400 hover:text-white hover:bg-white/5 rounded-full w-5 h-5 flex items-center justify-center transition-colors"
      >
        ×
      </button>
    </span>
  );
};

// Update the mention-tag style in mentionStyles
const mentionStyles = `
.mention-wrapper {
  display: inline-block;
  position: relative;
  margin: 0;
  padding: 0;
}

.mention-tag {
  display: inline;
  padding: 2px 4px;
  margin: 0 1px;
  font-weight: 500;
  background: rgba(239, 68, 68, 0.1); /* red-500 with 0.1 opacity */
  border-radius: 4px;
  color: rgb(239, 68, 68); /* red-500 */
  white-space: nowrap;
  cursor: default;
  user-select: none;
}

.mention-input {
  min-height: 44px;
  max-height: 200px;
  padding: 10px;
  width: 100%;
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.5;
  overflow-y: auto;
  resize: none;
  margin-bottom: 0;
}

.mention-suggestions {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  margin-bottom: 8px;
  background: #1a1a1a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
}

.mention-suggestion-item {
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.mention-suggestion-item:hover,
.mention-suggestion-item.selected {
  background-color: rgba(255, 255, 255, 0.1);
}

[contenteditable=true]:empty:before,
[contenteditable=true].empty:before {
  content: attr(placeholder);
  color: #6B7280;
  pointer-events: none;
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  left: 24px;  /* match the input's padding-left (px-6 = 1.5rem = 24px) */
  right: 24px;
}

/* Add styles to remove extra space after dividers */
.prose hr + h1,
.prose hr + h2,
.prose hr + h3,
.prose hr + h4,
.prose hr + h5,
.prose hr + h6 {
  margin-top: 0;
}
`;

// Add the styles to the document
const styleSheet = document.createElement("style");
styleSheet.textContent = mentionStyles;
document.head.appendChild(styleSheet);

export default Chat;